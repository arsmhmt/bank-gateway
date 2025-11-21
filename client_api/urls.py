
from django.urls import path
from . import views

urlpatterns = [
    path('cek/', views.withdraw_request_form, name='withdraw_request_form'),
]
