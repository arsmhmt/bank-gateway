
from django.urls import path
from . import views

urlpatterns = [
    path('deposit/init/', views.init_deposit, name='init_deposit'),
    path('withdraw/init/', views.init_withdraw, name='init_withdraw'),
]
