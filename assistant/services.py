import requests
from django.conf import settings


INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
COMPLETION_STATUSES = {
    "completed", "failed", "cancelled", "requires_action",
    "in_progress", "queued", "incomplete",
}
BLOCK_CODES = {
    "safety", "recitation", "language", "prohibited_content",
    "spii", "blocklist", "content_blocked",
}


class GeminiServiceError(Exception):
    """A local, public-safe explanation of a failed generation request."""

    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _invalid_response():
    return GeminiServiceError(
        "invalid_response",
        "The AI service returned an unreadable answer. Try sending your question again.",
        502,
    )


def _extract_answer(interaction):
    if not isinstance(interaction, dict):
        raise _invalid_response()

    status = interaction.get("status")
    if not isinstance(status, str) or status not in COMPLETION_STATUSES:
        raise _invalid_response()

    errors = interaction.get("errors", [])
    if not isinstance(errors, list) or any(not isinstance(error, dict) for error in errors):
        raise _invalid_response()
    if any(isinstance(error.get("code"), str) and error["code"] in BLOCK_CODES for error in errors):
        raise GeminiServiceError(
            "blocked_response",
            "The AI service could not answer that question. Try rephrasing it.",
            502,
        )
    if status == "incomplete":
        raise GeminiServiceError(
            "incomplete_response",
            "The answer could not finish. Try a shorter or more focused question.",
            502,
        )
    if status != "completed":
        raise GeminiServiceError(
            "upstream_error",
            "The AI service could not complete an answer. Try sending your question again.",
            502,
        )

    steps = interaction.get("steps")
    if not isinstance(steps, list):
        raise _invalid_response()
    last_output = None
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("type"), str):
            raise _invalid_response()
        if step["type"] == "model_output":
            last_output = step

    text_parts = []
    if last_output is not None:
        content = last_output.get("content")
        if not isinstance(content, list):
            raise _invalid_response()
        for block in content:
            if not isinstance(block, dict) or not isinstance(block.get("type"), str):
                raise _invalid_response()
            if block["type"] == "text":
                if not isinstance(block.get("text"), str):
                    raise _invalid_response()
                text_parts.append(block["text"])

    answer = "".join(text_parts)
    if not answer.strip():
        raise GeminiServiceError(
            "empty_response",
            "The AI service returned no answer. Try rephrasing your question.",
            502,
        )
    return answer


def generate_answer(prompt):
    """Generate one independent answer without storing or retrying the request."""
    api_key = settings.GEMINI_API_KEY.strip()
    model = settings.GEMINI_MODEL.strip()
    if not api_key or not model:
        raise GeminiServiceError(
            "configuration_error",
            "The AI service is not configured. Add a private Gemini API key and model on the server.",
            503,
        )

    try:
        response = requests.post(
            INTERACTIONS_URL,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "model": model,
                "input": prompt,
                "store": False,
                "stream": False,
                "generation_config": {"max_output_tokens": 2048, "thinking_level": "minimal"},
            },
            timeout=(5, 25),
            allow_redirects=False,
        )
    except requests.Timeout:
        raise GeminiServiceError(
            "timeout", "The AI service took too long to respond. Try again.", 504,
        ) from None
    except requests.RequestException:
        raise GeminiServiceError(
            "service_unavailable", "The AI service is unavailable. Check your connection and try again.", 503,
        ) from None

    if response.status_code in (401, 403, 404):
        raise GeminiServiceError(
            "configuration_error",
            "The AI service could not use the configured key or model. Check the private server settings.",
            503,
        )
    if response.status_code == 429:
        raise GeminiServiceError(
            "rate_limited", "The AI service quota is busy or exhausted. Wait a while before trying again.", 429,
        )
    if response.status_code >= 500:
        raise GeminiServiceError(
            "service_unavailable", "The AI service is temporarily unavailable. Try again later.", 503,
        )
    if not 200 <= response.status_code < 300:
        raise GeminiServiceError(
            "upstream_error", "The AI service could not accept the question. Try sending it again.", 502,
        )

    try:
        interaction = response.json()
    except (ValueError, RecursionError):
        raise _invalid_response() from None
    return _extract_answer(interaction)
