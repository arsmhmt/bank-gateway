from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from client_api import views as client_api_views
from public_gateway import views_bank, views_card, views_crypto

urlpatterns = [
    path('admin/', admin.site.urls),
    path('pay/<str:site_code>/<str:token>/', client_api_views.public_payment, name='public_payment'),
    path('pay/<str:site_code>/<str:token>/status/', client_api_views.public_payment_status, name='public_payment_status'),
    path("p/<slug:public_code>/deposit/", client_api_views.public_branch_deposit, name="public_branch_deposit"),
    path("p/<slug:public_code>/withdraw/", client_api_views.public_branch_withdraw, name="public_branch_withdraw"),
    path("p/<slug:code>/bank/deposit/", views_bank.deposit_form, name="public_bank_deposit"),
    path("p/<slug:code>/bank/withdraw/", views_bank.withdraw_form, name="public_bank_withdraw"),
    path("p/<slug:code>/card/deposit/", views_card.deposit_form, name="public_card_deposit"),
    path("p/<slug:code>/card/withdraw/", views_card.withdraw_form, name="public_card_withdraw"),
    path("p/<slug:code>/crypto/deposit/", views_crypto.deposit_form, name="public_crypto_deposit"),
    path("p/<slug:code>/crypto/withdraw/", views_crypto.withdraw_form, name="public_crypto_withdraw"),
    path('', TemplateView.as_view(template_name='index.html'), name='homepage'),
    path("yonetim/", include("admin_panel.urls")),      # Admin panel
    path("teminci/", include("provider_panel.urls")),   # Teminci panel
    path("site/", include("site_panel.urls")),          # Site/Branch panel
    path("api/", include("client_api.urls")),           # Dış API (legacy)
    path("api/v1/", include(("api.urls", "api"), namespace="api")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("django.contrib.auth.urls")),
]
