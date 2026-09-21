# orders/views.py
from functools import partial

from cart.cart import Cart
from catalog.models import Product
from catalog.notifications import maybe_send_low_stock_alert
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OrderCreateForm
from .models import InsufficientStockError, Order, OrderItem, OrderStatusHistory


@login_required
def order_create(request):
    cart = Cart(request)
    if len(cart) == 0:
        return redirect("cart:cart_detail")

    if request.method == "POST":
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = None
            try:
                with transaction.atomic():
                    # Lock the involved product rows in a stable (id) order
                    # so two concurrent checkouts sharing a product can't
                    # deadlock each other.
                    product_ids = sorted(int(item["product"].id) for item in cart)
                    locked_products = {
                        p.id: p
                        for p in Product.objects.select_for_update().filter(
                            id__in=product_ids
                        )
                    }

                    # Validate stock against the *locked* rows, not the
                    # possibly-stale objects the session cart was built from.
                    for item in cart:
                        product = locked_products[item["product"].id]
                        if product.stock < item["quantity"]:
                            raise InsufficientStockError(product)

                    order = form.save(commit=False)
                    order.user = request.user
                    order.save()  # generates order_number under this same lock
                    order = form.save(commit=False)
                    order.user = request.user
                    order.save()  # generates order_number under this same lock
                    OrderStatusHistory.objects.create(
                        order=order,
                        previous_status="",
                        new_status=order.status,
                        changed_by=request.user,
                    )

                    for item in cart:
                        product = locked_products[item["product"].id]
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            price=item["price"],
                            quantity=item["quantity"],
                        )
                        Product.objects.filter(id=product.id).update(
                            stock=F("stock") - item["quantity"]
                        )
                        transaction.on_commit(
                            partial(
                                maybe_send_low_stock_alert,
                                request,
                                product,
                                product.stock,  # value at lock time = stock before this decrement
                                item["quantity"],
                            )
                        )

                    cart.clear()
            except InsufficientStockError as exc:
                messages.error(
                    request,
                    f"Sorry, only {exc.product.stock} unit(s) of "
                    f"'{exc.product.name}' left in stock. Please update your cart.",
                )
                return redirect("cart:cart_detail")

            return redirect("orders:order_created", order_id=order.id)
    else:
        initial = {
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        }
        form = OrderCreateForm(initial=initial)

    return render(request, "orders/order_create.html", {"cart": cart, "form": form})


@login_required
def order_created(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "orders/order_created.html", {"order": order})


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "orders/order_list.html", {"orders": orders})