from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def role_required(*allowed_roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if getattr(user, "role", None) in allowed_roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to access this page.")
        return _wrapped
    return decorator


owner_admin_required = role_required("OWNER", "ADMIN")
branch_required = role_required("BRANCH")
provider_required = role_required("PROVIDER")
