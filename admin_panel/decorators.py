from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

# Import the new decorators from core
from core.decorators import owner_admin_required

# Keep backward compatibility alias
superadmin_required = owner_admin_required

def permission_required(perm_field):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if getattr(request.user, perm_field) or request.user.role in ('OWNER', 'ADMIN'):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view
    return decorator
