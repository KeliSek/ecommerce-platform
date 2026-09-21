# payments/views.py
import hashlib
import hmac
import json
import uuid

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from orders.models import Order

from .models import Payment

PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"


@login_required
def initiate_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status == "paid":
        return redirect("orders:order_list")

    reference = f"order_{order.id}_{uuid.uuid4().hex[:8]}"
    total_cost = order.get_total_cost()
    amount_pesewas = int(total_cost * 100)  # GHS -> pesewas

    payload = {
        "email": order.email,
        "amount": amount_pesewas,
        "currency": "GHS",
        "reference": reference,
        "callback_url": request.build_absolute_uri("/payments/verify/"),
        "metadata": {"order_id": order.id},
    }
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        PAYSTACK_INIT_URL, json=payload, headers=headers, timeout=10
    )
    data = response.json()

    if not data.get("status"):
        return render(
            request, "payments/payment_error.html", {"error": data.get("message")}
        )

    Payment.objects.update_or_create(
        order=order,
        defaults={"reference": reference, "amount": total_cost, "status": "pending"},
    )

    return redirect(data["data"]["authorization_url"])


def _mark_payment_success(reference, verified_data):
    """
    Idempotently mark a payment (and its order) as paid.

    Called from BOTH verify_payment (the browser redirect, nice UX for the
    happy path) and paystack_webhook (the real source of truth — fires
    server-to-server regardless of what the customer's browser does). Either
    one might arrive first, or arrive twice; select_for_update() + the
    already-success short-circuit makes this safe to call twice for the same
    reference without double-processing.

    Returns (payment_or_None, outcome) where outcome is one of:
    "success", "already_processed", "amount_mismatch", "unknown_reference".
    """
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(reference=reference)
        except Payment.DoesNotExist:
            return None, "unknown_reference"

        if payment.status == "success":
            return payment, "already_processed"

        order = payment.order
        paid_amount = verified_data["amount"]
        expected_amount = int(order.get_total_cost() * 100)

        if paid_amount != expected_amount:
            payment.status = "failed"
            payment.save(update_fields=["status"])
            return payment, "amount_mismatch"

        payment.status = "success"
        payment.save(update_fields=["status"])
        order.status = "paid"
        order.save(update_fields=["status"])
        return payment, "success"


@login_required
def verify_payment(request):
    reference = request.GET.get("reference") or request.GET.get("trxref")
    if not reference:
        return render(
            request, "payments/payment_error.html", {"error": "No reference provided."}
        )

    payment = get_object_or_404(Payment, reference=reference, order__user=request.user)

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    response = requests.get(
        f"{PAYSTACK_VERIFY_URL}{reference}", headers=headers, timeout=10
    )
    data = response.json()

    if not (data.get("status") and data["data"]["status"] == "success"):
        Payment.objects.filter(reference=reference, status="pending").update(
            status="failed"
        )
        return render(
            request, "payments/payment_error.html", {"error": "Payment not verified."}
        )

    payment, outcome = _mark_payment_success(reference, data["data"])

    if outcome in ("success", "already_processed"):
        return render(
            request, "payments/payment_success.html", {"order": payment.order}
        )

    return render(request, "payments/payment_error.html", {"error": "Amount mismatch."})


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """
    Paystack's server-to-server callback — the real source of truth for
    payment status. verify_payment above is just a nicer UX for the happy
    path where the customer's browser makes it back to your site; if they
    close the tab right after paying, this webhook is what actually marks
    the order paid.

    Must be registered as the webhook URL in your Paystack dashboard
    (Settings > API Keys & Webhooks). No login_required: Paystack's servers
    call this directly, not the customer's browser. CSRF-exempt for the same
    reason — the HMAC signature check below is what proves authenticity.
    """
    signature = request.headers.get("x-paystack-signature", "")
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        request.body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(signature, computed):
        return HttpResponseForbidden("Invalid signature")

    event = json.loads(request.body)

    if event.get("event") == "charge.success":
        _mark_payment_success(event["data"]["reference"], event["data"])

    # Always 200 once the signature checks out, even for events we ignore —
    # Paystack retries (with backoff) on anything else, which we don't want.
    return HttpResponse(status=200)
