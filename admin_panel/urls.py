from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    # Client Site & API Key Management
    path("clients/add/", views.add_client_site, name="add_client_site"),
    path("clients/list/", views.list_client_sites, name="list_client_sites"),
    path("clients/<int:site_id>/edit/", views.edit_client_site, name="edit_client_site"),
    path("clients/<int:site_id>/delete/", views.delete_client_site, name="delete_client_site"),
    path("api-keys/", views.api_keys_view, name="manage_api_keys"),
    path("api-keys/generate/<int:client_id>/", views.generate_api_key, name="generate_api_key"),
    path('login/', views.admin_login, name='login'),
    path("bekleyen-yatirimlar/", views.pending_deposits, name="admin_pending_deposits"),
    path("yatirim/onayla/<int:deposit_id>/", views.approve_deposit, name="approve_deposit"),
    path("yatirim/reddet/<int:deposit_id>/", views.reject_deposit, name="reject_deposit"),
    path("bekleyen-cekimler/", views.pending_withdrawals, name="admin_pending_withdrawals"),
    path("clients/add/", views.add_client_site, name="add_client_site"),
    path("clients/list/", views.list_client_sites, name="list_client_sites"),
    path("providers/add/", views.add_provider, name="add_provider"),
    path('teminciler/', views.provider_list, name='provider_list'),
    path('teminci/<int:provider_id>/edit/', views.edit_provider, name='edit_provider'),
    path('teminci/<int:provider_id>/delete/', views.delete_provider, name='delete_provider'),

    path("providers/commissions/", views.provider_commissions, name="provider_commissions"),
    path("providers/commissions/pay/<int:commission_id>/", views.mark_commission_paid, name="mark_commission_paid"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
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
    path("admins/logs/", views.admin_logs, name="admin_logs"),

# Bank account management (new RESTful style)
    path("bank-accounts/", views.list_bank_accounts, name="list_bank_accounts"),
    path("bank-accounts/add/", views.add_bank_account, name="add_bank_account"),
    path("bank-accounts/edit/<int:account_id>/", views.edit_bank_account, name="edit_bank_account"),
    path("bank-accounts/<int:account_id>/delete/", views.delete_bank_account, name="delete_bank_account"),

    # Financial reports
    path("finansal-raporlar/", views.financial_reports, name="financial_reports"),

    # Provider financial report
    path("teminci-raporlari/", views.provider_report, name="provider_report"),


]
