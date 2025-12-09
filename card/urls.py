from django.urls import path

from . import views

app_name = "card"

urlpatterns = [
    path("psp/<int:payment_id>/pending/", views.psp_pending, name="card_psp_pending"),
    path("psp/<int:payment_id>/callback/", views.psp_callback, name="card_psp_callback"),
]
