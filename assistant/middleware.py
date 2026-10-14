from .views import MAX_REQUEST_BYTES, _api_error


class ApiRequestBoundaryMiddleware:
    """Reject unsupported POST bodies before CSRF attempts to parse form data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/api/ask/" and request.method == "POST":
            declared_length = request.META.get("CONTENT_LENGTH")
            if declared_length not in (None, ""):
                try:
                    size = int(declared_length)
                except (TypeError, ValueError):
                    size = -1
                if size < 0:
                    return _api_error("invalid_request", "The request could not be read. Try again.", 400)
                if size > MAX_REQUEST_BYTES:
                    return _api_error(
                        "request_too_large", "The request is too large. Send a shorter question.", 413,
                    )
            if request.content_type != "application/json":
                return _api_error("unsupported_media_type", "Send the question as JSON.", 415)
        return self.get_response(request)
