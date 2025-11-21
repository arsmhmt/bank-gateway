
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='index.html'), name='homepage'),
    path('teminci/', include('provider_panel.urls')),  # Provider Panel
    path('yonetim/', include('admin_panel.urls')),     # Admin Panel (if implemented)
    path('api/', include('client_api.urls')),          # Public Client API (deposit request UI etc.)
]
