
from django.urls import path
from api import views

urlpatterns = [
    # backwards-compatible endpoints (kept)
    path('deposit/init/', views.init_deposit, name='init_deposit'),
    path('withdraw/init/', views.init_withdraw, name='init_withdraw'),

    # New API v1 endpoints
    path('deposit/create/', views.deposit_create, name='api_deposit_create'),
    path('withdraw/create/', views.withdraw_create, name='api_withdraw_create'),
    path('transaction/status/', views.transaction_status, name='api_transaction_status'),
]
