from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional

from django.conf import settings
from django.core.cache import cache

from .models import PublicRequestLog


@dataclass
class RateLimitInfo:
    is_limited: bool
    scope: Optional[str] = None
    retry_after: int = 0


def get_client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:512]


def build_request_fingerprint(request) -> str:
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    salt = getattr(settings, "PUBLIC_FORM_FINGERPRINT_SALT", "")
    raw = f"{ip}|{ua}|{accept}|{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _increment_counter(key: str, window: int) -> int:
    window = max(window, 1)
    current = cache.get(key)
    if current is None:
        cache.set(key, 1, window)
        return 1
    current = int(current) + 1
    cache.set(key, current, window)
    return current


def check_public_rate_limits(branch, request, request_type: str) -> RateLimitInfo:
    """
    Apply simple cache-backed rate limiting:
    - per IP per branch
    - per branch (all traffic)
    """

    window = int(getattr(settings, "PUBLIC_FORM_RATE_WINDOW_SECONDS", 300))
    ip_limit = int(getattr(settings, "PUBLIC_FORM_IP_RATE_LIMIT", 30))
    branch_limit = int(getattr(settings, "PUBLIC_FORM_BRANCH_RATE_LIMIT", 120))

    branch_id = getattr(branch, "id", None) or "anon"
    ip_address = get_client_ip(request) or "unknown"

    if ip_limit > 0:
        ip_key = f"public_rate:ip:{branch_id}:{ip_address}"
        ip_hits = _increment_counter(ip_key, window)
        if ip_hits > ip_limit:
            return RateLimitInfo(is_limited=True, scope="ip", retry_after=window)

    if branch_limit > 0:
        branch_key = f"public_rate:branch:{branch_id}"
        branch_hits = _increment_counter(branch_key, window)
        if branch_hits > branch_limit:
            return RateLimitInfo(is_limited=True, scope="branch", retry_after=window)

    return RateLimitInfo(is_limited=False)


def log_public_request(
    branch,
    request_type: str,
    request,
    *,
    was_limited: bool = False,
    limit_scope: str = "",
    metadata: Optional[Dict] = None,
):
    metadata = metadata or {}
    PublicRequestLog.objects.create(
        branch=branch,
        request_type=request_type,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        fingerprint=build_request_fingerprint(request),
        path=(request.path or "")[:255],
        was_limited=was_limited,
        limit_scope=limit_scope or "",
        metadata=metadata,
    )
