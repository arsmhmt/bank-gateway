from django.urls import path
from . import views

app_name = 'provider_panel'

urlpatterns = [
    path('dashboard/', views.provider_dashboard, name='provider_dashboard'),
    path('notifications/feed/', views.notifications_feed, name='notifications_feed'),
    path('pending-deposits/', views.pending_deposits, name='pending_deposits'),
    path('pending-deposits/<int:deposit_id>/approve/', views.approve_deposit, name='approve_deposit'),
    path('pending-deposits/<int:deposit_id>/reject/', views.reject_deposit, name='reject_deposit'),
    path('pending-withdrawals/', views.pending_withdrawals, name='pending_withdrawals'),
    path('bank/add/', views.add_bank_account, name='add_bank_account'),
    path('bank/list/', views.list_bank_accounts, name='list_bank_accounts'),
    path('finance/', views.provider_finance_report, name='finance_report'),
    path('finance/commissions/', views.provider_commissions, name='provider_commissions'),
    path('finance/history/', views.finance_history, name='finance_history'),
    path('profile/', views.provider_profile, name='provider_profile'),
    path('logout/', views.provider_logout, name='provider_logout'),
    path('login/', views.provider_login, name='provider_login'),
    path('bank/all/', views.bank_list, name='bank_list'),
    path('bank/edit/<int:pk>/', views.edit_bank_account, name='edit_bank_account'),
    path('bank/delete/<int:pk>/', views.bank_delete_confirm, name='bank_delete_confirm'),
    path('bank/form/', views.bank_form, name='bank_form'),
    path('deposit/requests/', views.deposit_requests, name='deposit_requests'),
    path('withdrawals/', views.withdrawals, name='withdrawals'),
    path('transactions/', views.transactions, name='transactions'),
]
