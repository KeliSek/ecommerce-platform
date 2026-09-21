# payments/urls.py
from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<int:order_id>/", views.initiate_payment, name="initiate_payment"),
    path("verify/", views.verify_payment, name="verify_payment"),
    path("webhook/", views.paystack_webhook, name="webhook"),
]
