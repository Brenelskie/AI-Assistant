import json

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.http import require_safe

from .services import GeminiServiceError, generate_answer


MAX_REQUEST_BYTES = 32 * 1024


def _api_response(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _api_error(code, message, status):
    return _api_response({"error": {"code": code, "message": message}}, status)


def _method_error(allowed):
    response = _api_error("method_not_allowed", f"Use {allowed} for this endpoint.", 405)
    response["Allow"] = allowed
    return response


def csrf_failure(request, reason=""):
    return _api_error(
        "csrf_failed",
        "The request could not be verified. Try sending your question again.",
        403,
    )


def home(request):
    return render(request, "assistant/index.html")


@require_safe
def manifest(request):
    return JsonResponse({
        "id": "/",
        "name": "AI Assistant",
        "short_name": "AI Assistant",
        "description": "A simple classroom assistant powered by Gemini.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f3f4f5",
        "theme_color": "#17212b",
        "lang": "en",
        "icons": [
            {"src": f"/static/assistant/img/icon-{size}.png", "sizes": f"{size}x{size}",
             "type": "image/png", "purpose": "any"}
            for size in (192, 512)
        ],
    }, content_type="application/manifest+json")


@require_safe
def serviceworker(request):
    from django.http import HttpResponse

    source = settings.BASE_DIR / "static/assistant/js/serviceworker.js"
    response = HttpResponse(source.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


def csrf_token(request):
    if request.method != "GET":
        return _method_error("GET")
    return _api_response({"csrfToken": get_token(request)})


def ask(request):
    if request.method != "POST":
        return _method_error("POST")
    if request.content_type != "application/json":
        return _api_error("unsupported_media_type", "Send the question as JSON.", 415)

    try:
        body = request.body
    except RequestDataTooBig:
        return _api_error("request_too_large", "The request is too large. Send a shorter question.", 413)
    if len(body) > MAX_REQUEST_BYTES:
        return _api_error("request_too_large", "The request is too large. Send a shorter question.", 413)

    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, RecursionError):
        return _api_error("invalid_json", "The question could not be read. Send valid JSON text.", 400)

    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str):
        return _api_error("invalid_prompt", "Enter a question as text.", 400)
    prompt = prompt.strip()
    if not prompt or len(prompt) > settings.MAX_PROMPT_LENGTH:
        return _api_error(
            "invalid_prompt", f"Enter a question between 1 and {settings.MAX_PROMPT_LENGTH:,} characters.", 400,
        )

    try:
        answer = generate_answer(prompt)
    except GeminiServiceError as error:
        return _api_error(error.code, error.message, error.status_code)
    return _api_response({"answer": answer, "model": settings.GEMINI_MODEL.strip()})
