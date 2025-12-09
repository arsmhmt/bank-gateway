from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    # Root - redirect to dashboard
    path("", views.admin_dashboard, name="index"),

    # Site Management & API keys
    path("panel/", views.admin_dashboard, name="panel"),
    path("siteler/", views.list_client_sites, name="siteler_list"),
    path("siteler/ekle/", views.add_client_site, name="site_ekle"),
    # legacy alias used by some templates
    path("siteler/ekle/", views.add_client_site, name="add_client_site"),
    path("siteler/<int:branch_id>/", views.site_detail, name="site_detay"),
    path("siteler/<int:site_id>/duzenle/", views.edit_client_site, name="site_duzenle"),
    path("siteler/<int:site_id>/sil/", views.delete_client_site, name="site_sil"),
    path("siteler/<int:site_id>/gecitler/", views.site_gateway_list, name="site_gateway_list"),
    path("siteler/<int:site_id>/gecitler/<str:gateway>/", views.site_gateway_edit, name="site_gateway_edit"),
    path("api-keys/", views.api_keys_view, name="manage_api_keys"),
    path("api-keys/generate/<int:client_id>/", views.generate_api_key, name="generate_api_key"),
    path('login/', views.admin_login, name='login'),
    path("banka/", views.banka_genel_bakis, name="banka_genel_bakis"),
    path("kripto/", views.kripto_genel_bakis, name="kripto_genel_bakis"),
    # Kripto Koinler (per-site coin accounts)
    path("kripto/koinler/", views.kripto_koin_list, name="kripto_koin_list"),
    path("kripto/koinler/yeni/", views.kripto_koin_create, name="kripto_koin_create"),
    path("kripto/koinler/<int:pk>/duzenle/", views.kripto_koin_edit, name="kripto_koin_edit"),
    path("kripto/koinler/<int:pk>/sil/", views.kripto_koin_delete, name="kripto_koin_delete"),
    path("kripto/siteler/<int:branch_id>/", views.kripto_site_detay, name="kripto_site_detay"),
    path("kredi-karti/", views.kredi_karti_genel_bakis, name="kredi_karti_genel_bakis"),
    path("kredi-karti/siteler/<int:branch_id>/", views.kredi_karti_site_detay, name="kredi_karti_site_detay"),
    path("bekleyen-yatirimlar/", views.pending_deposits, name="admin_pending_deposits"),
    path("yatirim/link-olustur/", views.create_deposit_link, name="create_deposit_link"),
    path("yatirim/onayla/<int:deposit_id>/", views.approve_deposit, name="approve_deposit"),
    path("yatirim/reddet/<int:deposit_id>/", views.reject_deposit, name="reject_deposit"),
    path("bekleyen-cekimler/", views.pending_withdrawals, name="admin_pending_withdrawals"),
    path("cekim/teminci-ata/<int:withdrawal_id>/", views.assign_withdrawal_provider, name="assign_withdrawal_provider"),
    path("teminci/ekle/", views.add_provider, name="add_provider"),
    path('teminciler/', views.provider_list, name='provider_list'),
    path('teminci/<int:provider_id>/edit/', views.edit_provider, name='edit_provider'),
    path('teminci/<int:provider_id>/delete/', views.delete_provider, name='delete_provider'),
    path('teminci/<int:provider_id>/', views.provider_detail, name='provider_detail'),
    path('teminci/<int:provider_id>/toggle-active/', views.toggle_provider_active, name='toggle_provider_active'),
    path('teminci/<int:provider_id>/add-settlement/', views.add_settlement_payment, name='add_settlement'),

    path("providers/commissions/", views.provider_commissions, name="provider_commissions"),
    path("providers/commissions/pay/<int:commission_id>/", views.mark_commission_paid, name="mark_commission_paid"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("gecitler/", views.gateway_matrix, name="gateways_matrix"),
    path("gecitler/<int:branch_id>/", views.gateway_branch_detail, name="gateway_branch_detail"),
    path("kripto/genel-bakis/", views.crypto_overview, name="crypto_overview"),
    path("profil/", views.admin_profile, name="admin_profile"),
    path("sifre-degistir/", views.change_admin_password, name="admin_change_password"),
    path("site-rapor/", views.site_finance_report, name="site_finance_report"),
    path("komisyon-rapor/", views.commission_report, name="commission_report"),
    path("admin/ekle/", views.add_admin, name="add_admin"),
    path("admin/yonetim/", views.manage_admins, name="manage_admins"),
    path("log-kayitlari/", views.admin_logs, name="admin_logs"),
    path("logout/", views.admin_logout, name="logout"),
    path("admins/", views.view_admins, name="manage_admins"),
    path("admins/add/", views.add_admin, name="add_admin"),
    path("admins/<int:admin_id>/edit/", views.edit_admin, name="edit_admin"),
    path("admins/<int:admin_id>/delete/", views.delete_admin, name="delete_admin"),
    path("admins/<int:admin_id>/toggle-status/", views.toggle_admin_status, name="toggle_admin_status"),
    path("admins/<int:admin_id>/reset-password/", views.reset_admin_password, name="reset_admin_password"),
    path("admins/logs/", views.admin_logs, name="admin_logs"),

# Bank account management (new RESTful style)
    path("bank-accounts/", views.list_bank_accounts, name="list_bank_accounts"),
    path("bank-accounts/add/", views.add_bank_account, name="add_bank_account"),
    path("bank-accounts/edit/<int:account_id>/", views.edit_bank_account, name="edit_bank_account"),
    path("bank-accounts/<int:account_id>/delete/", views.delete_bank_account, name="delete_bank_account"),
    path("bank-accounts/<int:account_id>/toggle-active/", views.toggle_bank_account_active, name="toggle_bank_account_active"),

    # Financial reports
    path("finansal-raporlar/", views.financial_reports, name="financial_reports"),

    # Provider financial report
    path("teminci-raporlari/", views.provider_report, name="provider_report"),
    path("transactions/", views.transactions_list, name="transactions_list"),
    # Crypto wallet configs
    path("kripto/cuzdanlar/", views.crypto_wallet_list, name="crypto_wallets"),
    path("kripto/cuzdanlar/ekle/", views.crypto_wallet_create, name="crypto_wallet_add"),
    path("kripto/cuzdanlar/<int:pk>/", views.crypto_wallet_edit, name="crypto_wallet_edit"),
]
