
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

def role_based_redirect(request):
    if request.user.is_authenticated:
        if request.user.role in ['admin', 'superadmin']:
            return redirect('/admin120724/dashboard/')
        elif request.user.role == 'teminci':
            return redirect('/provider/dashboard/')
    return redirect('/login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('redirect/', role_based_redirect, name='role_redirect'),
    path('admin120724/', include('admin_panel.urls')),
    path('provider/', include('provider_panel.urls')),
]
