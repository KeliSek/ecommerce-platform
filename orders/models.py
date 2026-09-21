# orders/models.py
import uuid
from typing import ClassVar

from catalog.models import Product
from django.conf import settings
from django.db import models
from django.utils import timezone


class OrderNumberCounter(models.Model):
    """
    One row per year. Locked with select_for_update() when handing out the
    next sequence number, so concurrent checkouts can never receive the same
    order number. Must be called from inside a transaction.atomic() block
    (order_create view wraps checkout in one).
    """

    year = models.PositiveIntegerField(unique=True)
    last_value = models.PositiveIntegerField(default=0)

    @classmethod
    def next_value(cls, year):
        counter, _ = cls.objects.select_for_update().get_or_create(
            year=year, defaults={"last_value": 0}
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
        return counter.last_value


class InsufficientStockError(Exception):
    """Raised inside the checkout transaction when a locked product no
    longer has enough stock to satisfy the cart. The view catches this and
    shows the customer a friendly message instead of oversell."""

    def __init__(self, product):
        self.product = product
        super().__init__(f"Insufficient stock for {product.name}")


class Order(models.Model):
    STATUS_CHOICES: ClassVar[tuple[tuple[str, str], ...]] = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )

    order_number = models.CharField(
        max_length=20, unique=True, blank=True, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    address = models.CharField(max_length=225)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number or f"Order {self.id}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    def _generate_order_number(self):
        year = timezone.now().year
        uuid_suffix = uuid.uuid4().hex[:8].upper()
        return f"AKORD{year}{uuid_suffix}"

    def get_total_cost(self):
        return sum(item.get_cost() for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, related_name="order_items", on_delete=models.CASCADE
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveBigIntegerField(default=1)

    def __str__(self):
        return str(self.id)

    def get_cost(self):
        return self.price * self.quantity


# orders/models.py — add below OrderItem
class OrderStatusHistory(models.Model):
    """
    One row per status transition. Written by both order_create (the
    initial pending status) and the vendor dashboard's order_update_status
    view, so the full lifecycle of an order is visible to staff without
    digging through logs.
    """

    order = models.ForeignKey(Order, related_name="status_history", on_delete=models.CASCADE)
    previous_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, blank=True)
    new_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name_plural = "Order status histories"

    def __str__(self):
        return f"{self.order.order_number}: {self.previous_status or '—'} → {self.new_status}"