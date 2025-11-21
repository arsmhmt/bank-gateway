from django.urls import path

from client_api import views

urlpatterns = [
    path('bankalar/', views.bank_accounts, name='bank_accounts'),
    path('banka/ekle/', views.add_bank_account, name='add_bank_account'),
    path('banka/<int:account_id>/duzenle/', views.edit_bank_account, name='edit_bank_account'),
    path('banka/<int:account_id>/sil/', views.delete_bank_account, name='delete_bank_account'),

]
