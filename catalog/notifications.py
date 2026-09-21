# catalog/notifications.py
"""
Email notifications for catalog events. Kept separate from views/models so
call sites (checkout, dashboard) can trigger a notification without pulling
in template/view concerns, and so this is easy to test or swap out later.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def maybe_send_low_stock_alert(request, product, stock_before, quantity_deducted):
    """
    Emails every vendor-admin, but only once per dip below the threshold —
    only when THIS decrement is what pushes stock from above the threshold
    to at-or-below it. Must be called after the checkout transaction
    commits (via transaction.on_commit), never inside it, so a mail hiccup
    can never roll back a paid order.
    """
    threshold = settings.LOW_STOCK_THRESHOLD
    stock_after = stock_before - quantity_deducted

    if stock_after > threshold or stock_before <= threshold:
        return  # either still fine, or it was already low before this sale

    from accounts.models import (
        User,  # local import avoids a hard import-order dependency
    )

    recipients = list(
        User.objects.filter(is_vendor_admin=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        logger.warning(
            "Low stock on '%s' (now %s left) but no vendor-admin has an email set.",
            product.name, stock_after,
        )
        return

    edit_url = request.build_absolute_uri(
        reverse("dashboard:product_update", args=[product.id])
    )
    subject = f"Low stock: {product.name} ({stock_after} left)"
    message = (
        f"'{product.name}' just dropped to {stock_after} unit(s) in stock "
        f"after a sale.\n\nReview and restock it here:\n{edit_url}\n"
    )

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception:
        # Never let an email hiccup affect the vendor-side view of a
        # checkout that has already committed successfully.
        logger.exception("Failed to send low-stock alert for '%s'.", product.name)