from django.contrib.auth.decorators import user_passes_test

def provider_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'provider')(view_func)

def superadmin_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'superadmin')(view_func)
