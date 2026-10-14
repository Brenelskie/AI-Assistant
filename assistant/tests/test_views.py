import json
from unittest.mock import Mock, patch

import requests
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, override_settings


@override_settings(GEMINI_API_KEY="private-test-key", GEMINI_MODEL="server-model")
class AssistantApiTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.post_patcher = patch("requests.post")
        self.post = self.post_patcher.start()
        self.addCleanup(self.post_patcher.stop)
        response = Mock(status_code=200)
        response.json.return_value = {
            "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": "Model answer"}]}],
        }
        self.post.return_value = response

    def bootstrap(self):
        response = self.client.get("/api/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(set(response.json()), {"csrfToken"})
        self.assertEqual(len(response.json()["csrfToken"]), 64)
        self.assertIn("csrftoken", self.client.cookies)
        return response.json()["csrfToken"]

    def ask(self, payload, content_type="application/json", **extra):
        token = self.bootstrap()
        body = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
        return self.client.post(
            "/api/ask/", data=body, content_type=content_type,
            HTTP_X_CSRFTOKEN=token, CONTENT_TYPE=content_type, **extra,
        )

    def assert_api_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(set(response.json()), {"error"})
        self.assertEqual(set(response.json()["error"]), {"code", "message"})
        self.assertEqual(response.json()["error"]["code"], code)
        self.assertIsInstance(response.json()["error"]["message"], str)
        self.assertNotIn("private-test-key", response.content.decode())
        self.assertNotIn("provider diagnostics", response.content.decode())

    def test_real_csrf_bootstrap_then_submission_returns_answer(self):
        response = self.ask({"prompt": "  Explain this. \n", "model": "browser-model"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Model answer", "model": "server-model"})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.post.assert_called_once()
        self.assertEqual(self.post.call_args.kwargs["json"]["input"], "Explain this.")
        self.assertEqual(self.post.call_args.kwargs["json"]["model"], "server-model")

    def test_tokenless_submission_is_rejected_by_real_middleware(self):
        response = self.client.post(
            "/api/ask/", data=json.dumps({"prompt": "Question"}), content_type="application/json"
        )
        self.assert_api_error(response, 403, "csrf_failed")
        self.post.assert_not_called()

    def test_cookie_without_header_token_is_rejected(self):
        self.bootstrap()
        response = self.client.post(
            "/api/ask/", data=json.dumps({"prompt": "Question"}), content_type="application/json"
        )
        self.assert_api_error(response, 403, "csrf_failed")
        self.post.assert_not_called()

    def test_invalid_csrf_token_is_rejected(self):
        self.bootstrap()
        response = self.client.post(
            "/api/ask/", data=json.dumps({"prompt": "Question"}),
            content_type="application/json", HTTP_X_CSRFTOKEN="invalid",
        )
        self.assert_api_error(response, 403, "csrf_failed")
        self.post.assert_not_called()

    def test_bootstrap_can_refresh_after_cookie_removal(self):
        first_token = self.bootstrap()
        self.client.cookies.clear()
        second_token = self.bootstrap()
        self.assertNotEqual(first_token, second_token)
        response = self.client.post(
            "/api/ask/", data=json.dumps({"prompt": "Question"}),
            content_type="application/json", HTTP_X_CSRFTOKEN=second_token,
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_methods_are_json_and_noncacheable(self):
        token = self.bootstrap()
        for method in ("get", "put", "delete", "head", "options"):
            with self.subTest(endpoint="ask", method=method):
                response = getattr(self.client, method)("/api/ask/", HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Cache-Control"], "no-store")
                self.assertEqual(response["Allow"], "POST")
                if method != "head":
                    self.assert_api_error(response, 405, "method_not_allowed")
        for method in ("post", "put", "delete", "head", "options"):
            with self.subTest(endpoint="csrf", method=method):
                response = getattr(self.client, method)("/api/csrf/", HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Cache-Control"], "no-store")
                self.assertEqual(response["Allow"], "GET")
                if method != "head":
                    self.assert_api_error(response, 405, "method_not_allowed")
        self.post.assert_not_called()

    def test_nonjson_content_types_are_rejected(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "text/json"):
            with self.subTest(content_type=content_type):
                response = self.ask('{"prompt":"Question"}', content_type)
                self.assert_api_error(response, 415, "unsupported_media_type")
        self.post.assert_not_called()

    def test_json_content_type_with_charset_is_accepted(self):
        response = self.ask({"prompt": "Question"}, "application/json; charset=utf-8")
        self.assertEqual(response.status_code, 200)

    def test_invalid_json_or_encoding_is_controlled(self):
        for body in (
            "", "{", '{"prompt":}', b'\xff', "[" * 10000 + "]" * 10000,
            '{"prompt":' + "9" * 5000 + "}",
        ):
            with self.subTest(body_type=type(body).__name__, body_length=len(body)):
                response = self.ask(body)
                self.assert_api_error(response, 400, "invalid_json")
        self.post.assert_not_called()

    def test_prompt_must_be_nonempty_text_in_a_json_object(self):
        bodies = [
            "null", "123", '"question"', [], {},
            {"prompt": None}, {"prompt": 1}, {"prompt": False},
            {"prompt": []}, {"prompt": {}}, {"prompt": ""}, {"prompt": " \n\t"},
        ]
        for body in bodies:
            with self.subTest(body=body):
                response = self.ask(body)
                self.assert_api_error(response, 400, "invalid_prompt")
        self.post.assert_not_called()

    def test_prompt_limit_applies_after_trimming(self):
        response = self.ask({"prompt": "  " + "x" * 4000 + " \n"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.post.call_args.kwargs["json"]["input"]), 4000)
        self.post.reset_mock()
        response = self.ask({"prompt": "x" * 4001})
        self.assert_api_error(response, 400, "invalid_prompt")
        self.post.assert_not_called()

    def test_oversize_request_returns_controlled_json(self):
        response = self.ask('{"prompt":"Question","padding":"' + "x" * (32 * 1024) + '"}')
        self.assert_api_error(response, 413, "request_too_large")
        self.post.assert_not_called()

    def test_request_limit_is_enforced_even_if_django_body_limit_is_higher(self):
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            response = self.ask('{"prompt":"Question","padding":"' + "x" * (32 * 1024) + '"}')
        self.assert_api_error(response, 413, "request_too_large")
        self.post.assert_not_called()

    def test_missing_key_returns_safe_noncacheable_configuration_error(self):
        with override_settings(GEMINI_API_KEY=""):
            response = self.ask({"prompt": "Question"})
        self.assert_api_error(response, 503, "configuration_error")
        self.post.assert_not_called()

    def test_provider_errors_remain_local_at_api_boundary(self):
        cases = [(401, 503, "configuration_error"), (403, 503, "configuration_error"),
                 (404, 503, "configuration_error"), (429, 429, "rate_limited"),
                 (500, 503, "service_unavailable"), (400, 502, "upstream_error")]
        for upstream_status, public_status, code in cases:
            with self.subTest(upstream_status=upstream_status):
                self.post.return_value.status_code = upstream_status
                self.post.return_value.json.return_value = {"error": {"message": "provider diagnostics private-test-key"}}
                response = self.ask({"prompt": "Question"})
                self.assert_api_error(response, public_status, code)

    def test_timeout_returns_safe_noncacheable_error(self):
        self.post.side_effect = requests.Timeout("provider diagnostics private-test-key")
        response = self.ask({"prompt": "Question"})
        self.assert_api_error(response, 504, "timeout")

    def test_malformed_provider_reply_returns_safe_noncacheable_error(self):
        self.post.return_value.json.side_effect = ValueError("provider diagnostics private-test-key")
        response = self.ask({"prompt": "Question"})
        self.assert_api_error(response, 502, "invalid_response")

    def test_literal_prompt_and_reply_survive_json_boundary(self):
        markup = "<script>alert('literal')</script>"
        self.post.return_value.json.return_value["steps"][0]["content"][0]["text"] = markup
        response = self.ask({"prompt": markup})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], markup)
        self.assertEqual(self.post.call_args.kwargs["json"]["input"], markup)


@override_settings(MIDDLEWARE=[
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "assistant.middleware.ApiRequestBoundaryMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
])
class ApiRequestBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def assert_safe_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.json()["error"]["code"], code)

    def test_oversized_form_is_rejected_before_csrf_parses_it(self):
        token = self.client.get("/api/csrf/").json()["csrfToken"]
        with patch("requests.post") as post:
            response = self.client.post(
                "/api/ask/", data="padding=" + "x" * (32 * 1024),
                content_type="application/x-www-form-urlencoded", HTTP_X_CSRFTOKEN=token,
            )
        self.assert_safe_error(response, 413, "request_too_large")
        post.assert_not_called()

    def test_tokenless_oversized_form_is_still_a_safe_size_error(self):
        response = self.client.post(
            "/api/ask/", data="padding=" + "x" * (32 * 1024),
            content_type="application/x-www-form-urlencoded",
        )
        self.assert_safe_error(response, 413, "request_too_large")

    def test_unsupported_media_is_rejected_before_form_parsing(self):
        # More fields than Django's form parser permits must never reach that parser.
        response = self.client.post(
            "/api/ask/", data="&".join(f"field{i}=x" for i in range(1100)),
            content_type="application/x-www-form-urlencoded",
        )
        self.assert_safe_error(response, 415, "unsupported_media_type")

    def test_invalid_declared_lengths_are_controlled(self):
        for length in ("invalid", "-1", "1.5", "1, 2"):
            with self.subTest(length=length):
                response = self.client.post(
                    "/api/ask/", data='{"prompt":"Question"}',
                    content_type="application/json", CONTENT_LENGTH=length,
                )
                self.assert_safe_error(response, 400, "invalid_request")

    def test_valid_json_still_requires_real_csrf_protection(self):
        with patch("requests.post") as post:
            response = self.client.post(
                "/api/ask/", data='{"prompt":"Question"}', content_type="application/json",
            )
        self.assert_safe_error(response, 403, "csrf_failed")
        post.assert_not_called()

    def test_missing_or_empty_declared_length_defers_to_body_validation(self):
        from assistant.middleware import ApiRequestBoundaryMiddleware

        for length in (None, ""):
            with self.subTest(length=length):
                request = RequestFactory().post(
                    "/api/ask/", data='{"prompt":"Question"}', content_type="application/json",
                )
                if length is None:
                    del request.META["CONTENT_LENGTH"]
                else:
                    request.META["CONTENT_LENGTH"] = length
                downstream = Mock(return_value=HttpResponse("downstream"))
                response = ApiRequestBoundaryMiddleware(downstream)(request)
                self.assertEqual(response.content, b"downstream")
                downstream.assert_called_once_with(request)

    def test_guard_does_not_change_other_routes_or_methods(self):
        from assistant.middleware import ApiRequestBoundaryMiddleware

        for method, path in (("GET", "/api/ask/"), ("POST", "/outside/"), ("GET", "/api/csrf/")):
            with self.subTest(method=method, path=path):
                request = RequestFactory().generic(method, path, content_type="text/plain")
                downstream = Mock(return_value=HttpResponse("downstream"))
                response = ApiRequestBoundaryMiddleware(downstream)(request)
                self.assertEqual(response.content, b"downstream")
                downstream.assert_called_once_with(request)
