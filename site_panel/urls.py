from django.urls import path
from . import views

app_name = "site_panel"

urlpatterns = [
    path("login/", views.site_login, name="login"),
    path("logout/", views.site_logout, name="site_logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("banka-havale/", views.deposit_list, name="banka_havale"),
    path("kripto-odeme/", views.crypto_wallets, name="kripto_odeme"),
    path("kripto-cuzdanlar/", views.crypto_wallets, name="kripto_cuzdanlar"),
    path("kart-ayarlari/", views.kart_ayarlari, name="kart_ayarlari"),
    path("kredi-karti/", views.kart_ayarlari, name="kredi_karti"),
    path("card-settings/", views.card_settings, name="card_settings"),  # legacy alias
    path("crypto-wallets/", views.crypto_wallets, name="crypto_wallets"),  # legacy alias
    path("deposits/", views.deposit_list, name="deposits"),
    path("withdrawals/", views.withdrawal_list, name="withdrawals"),
    path("bank-accounts/", views.bank_accounts, name="bank_accounts"),
    path("reports/", views.reports, name="reports"),
    path("link-olustur/", views.create_deposit_link, name="create_link"),
    path("notifications/feed/", views.notifications_feed, name="notifications_feed"),
    path("notifications/settings/", views.update_notification_settings, name="update_notification_settings"),
    path("api-yonetimi/", views.api_yonetimi, name="api_yonetimi"),
]
