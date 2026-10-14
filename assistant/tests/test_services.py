from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from assistant.services import GeminiServiceError, generate_answer


def completed_response(*blocks):
    return {
        "status": "completed",
        "steps": [{"type": "model_output", "content": list(blocks)}],
    }


@override_settings(GEMINI_API_KEY="private-test-key", GEMINI_MODEL="server-model")
class GeminiServiceTests(SimpleTestCase):
    def setUp(self):
        self.post_patcher = patch("assistant.services.requests.post")
        self.post = self.post_patcher.start()
        self.addCleanup(self.post_patcher.stop)
        self.response = Mock(status_code=200)
        self.response.json.return_value = completed_response(
            {"type": "text", "text": "An answer."}
        )
        self.post.return_value = self.response

    def assert_service_error(self, code, status):
        with self.assertRaises(GeminiServiceError) as caught:
            generate_answer("A private question")
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.status_code, status)
        self.assertEqual(str(error), error.message)
        self.assertNotIn("private-test-key", error.message)
        self.assertNotIn("A private question", error.message)
        self.assertNotIn("provider diagnostics", error.message)
        return error

    def test_sends_one_stateless_bounded_request_with_server_configuration(self):
        self.assertEqual(generate_answer("Explain photosynthesis."), "An answer.")
        self.post.assert_called_once_with(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": "private-test-key",
                "Content-Type": "application/json",
            },
            json={
                "model": "server-model",
                "input": "Explain photosynthesis.",
                "store": False,
                "stream": False,
                "generation_config": {
                    "max_output_tokens": 2048,
                    "thinking_level": "minimal",
                },
            },
            timeout=(5, 25),
            allow_redirects=False,
        )

    def test_joins_only_text_in_last_model_output_and_excludes_thoughts(self):
        self.response.json.return_value = {
            "status": "completed",
            "output_text": "SDK-only convenience value",
            "steps": [
                {"type": "thought", "summary": [{"type": "text", "text": "Secret thought"}]},
                {"type": "model_output", "content": [{"type": "text", "text": "Old answer"}]},
                {"type": "model_output", "content": [
                    {"type": "text", "text": "First part. "},
                    {"type": "thought", "text": "Another thought"},
                    {"type": "image", "data": "image-data"},
                    {"type": "text", "text": "Second part."},
                ]},
                {"type": "thought", "summary": [{"type": "text", "text": "Trailing thought"}]},
            ],
        }
        self.assertEqual(generate_answer("Question"), "First part. Second part.")

    def test_preserves_literal_output_text(self):
        self.response.json.return_value = completed_response(
            {"type": "text", "text": "  <script>alert('literal')</script>\n"}
        )
        self.assertEqual(generate_answer("Question"), "  <script>alert('literal')</script>\n")

    def test_missing_key_does_not_call_provider(self):
        with override_settings(GEMINI_API_KEY=""):
            self.assert_service_error("configuration_error", 503)
        self.post.assert_not_called()

    def test_missing_model_does_not_call_provider(self):
        with override_settings(GEMINI_MODEL="  "):
            self.assert_service_error("configuration_error", 503)
        self.post.assert_not_called()

    def test_http_failures_use_local_messages_and_never_retry(self):
        cases = [
            (401, "configuration_error", 503),
            (403, "configuration_error", 503),
            (404, "configuration_error", 503),
            (429, "rate_limited", 429),
            (500, "service_unavailable", 503),
            (503, "service_unavailable", 503),
            (400, "upstream_error", 502),
            (302, "upstream_error", 502),
        ]
        for provider_status, code, public_status in cases:
            with self.subTest(provider_status=provider_status):
                self.post.reset_mock()
                self.response.status_code = provider_status
                self.response.json.return_value = {
                    "error": {"message": "provider diagnostics private-test-key"}
                }
                self.assert_service_error(code, public_status)
                self.post.assert_called_once()

    def test_transport_timeouts_are_safe_and_not_retried(self):
        for exception in (requests.ConnectTimeout, requests.ReadTimeout):
            with self.subTest(exception=exception.__name__):
                self.post.reset_mock()
                self.post.side_effect = exception("provider diagnostics private-test-key")
                self.assert_service_error("timeout", 504)
                self.post.assert_called_once()

    def test_transport_connection_failure_is_safe(self):
        self.post.side_effect = requests.ConnectionError("provider diagnostics private-test-key")
        self.assert_service_error("service_unavailable", 503)
        self.post.assert_called_once()

    def test_other_request_failure_is_safe(self):
        self.post.side_effect = requests.RequestException("provider diagnostics private-test-key")
        self.assert_service_error("service_unavailable", 503)
        self.post.assert_called_once()

    def test_malformed_provider_json_is_safe(self):
        for exception in (ValueError, RecursionError):
            with self.subTest(exception=exception.__name__):
                self.response.json.side_effect = exception("provider diagnostics private-test-key")
                self.assert_service_error("invalid_response", 502)

    def test_malformed_wire_shapes_are_controlled(self):
        cases = [
            None,
            [],
            "provider diagnostics",
            {},
            {"interaction": completed_response({"type": "text", "text": "Wrong envelope"})},
            {"status": "completed", "output_text": "SDK-only value"},
            {"status": "completed", "steps": None},
            {"status": "completed", "steps": {}},
            {"status": "completed", "steps": ["not a step"]},
            {"status": "completed", "steps": [{"content": []}]},
            {"status": "completed", "steps": [{"type": "model_output", "content": {}}]},
            completed_response("not a content block"),
            completed_response({"type": "text"}),
            completed_response({"type": "text", "text": 123}),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                self.assert_service_error("invalid_response", 502)

    def test_known_noncompleted_statuses_are_controlled(self):
        cases = [
            ("incomplete", "incomplete_response"),
            ("failed", "upstream_error"),
            ("cancelled", "upstream_error"),
            ("requires_action", "upstream_error"),
            ("in_progress", "upstream_error"),
            ("queued", "upstream_error"),
        ]
        for status, code in cases:
            with self.subTest(status=status):
                self.response.json.return_value = {
                    "status": status,
                    "steps": [{"type": "model_output", "content": [{"type": "text", "text": "Partial"}]}],
                }
                self.assert_service_error(code, 502)

    def test_blocked_results_are_controlled_without_diagnostics(self):
        for code in ("safety", "recitation", "language", "prohibited_content", "spii", "blocklist", "content_blocked"):
            with self.subTest(code=code):
                self.response.json.return_value = {
                    "status": "failed",
                    "errors": [{"code": code, "message": "provider diagnostics private-test-key"}],
                    "steps": [],
                }
                self.assert_service_error("blocked_response", 502)

    def test_unknown_or_nonstring_status_is_malformed(self):
        for status in ("not-a-status", None, 123, []):
            with self.subTest(status=status):
                self.response.json.return_value = {"status": status, "steps": []}
                self.assert_service_error("invalid_response", 502)

    def test_empty_output_does_not_fall_back_to_an_earlier_answer(self):
        cases = [
            {"status": "completed", "steps": []},
            {"status": "completed", "steps": [{"type": "thought", "summary": [{"type": "text", "text": "Thought"}]}]},
            completed_response(),
            completed_response({"type": "text", "text": " \n\t"}),
            completed_response({"type": "image", "data": "image-data"}),
            {"status": "completed", "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": "Earlier answer"}]},
                {"type": "model_output", "content": []},
            ]},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                self.assert_service_error("empty_response", 502)
