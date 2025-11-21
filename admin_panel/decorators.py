from django.contrib.auth.decorators import user_passes_test

def is_superadmin(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'superadmin'

superadmin_required = user_passes_test(is_superadmin)

from django.core.exceptions import PermissionDenied

def permission_required(perm_field):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if getattr(request.user, perm_field) or request.user.role == 'superadmin':
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view
    return decorator
