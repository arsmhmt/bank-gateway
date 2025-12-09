from django.http import JsonResponse


def api_success(data=None, status=200, message=""):
    """Return a successful JSON envelope.

    Canonical fields:
    - success: bool
    - code: machine-readable code ("OK" for success)
    - message: human readable message (optional)
    - data: payload object
    """
    payload = {
        "success": True,
        "code": "OK",
        "message": message or "",
        "data": data or {},
    }
    return JsonResponse(payload, status=status)


def api_error(code: str, message: str, status=400, data=None, extra=None):
    """Return an error JSON envelope.

    - `code` is the canonical machine-readable error code (string).
    - For backward compatibility, we also include `error_code` with the same value.
    - `data` can be used to include structured details (e.g., field errors).
    - `extra` allows adding arbitrary top-level keys when needed.
    """
    payload = {
        "success": False,
        "code": code,
        "error_code": code,  # legacy alias for older clients
        "message": message,
        "data": data or None,
    }
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)
