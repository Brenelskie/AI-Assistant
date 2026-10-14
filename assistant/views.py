def csrf_failure(request, reason=""):
    from django.http import JsonResponse

    response = JsonResponse({"error": {
        "code": "csrf_failed",
        "message": "The request could not be verified. Try sending your question again.",
    }}, status=403)
    response["Cache-Control"] = "no-store"
    return response
