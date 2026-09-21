# cart/views.py
from catalog.models import Product
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import CartAddProductForm


def _add_to_cart(request, product, quantity, override):
    cart = Cart(request)
    current_qty = cart.cart.get(str(product.id), {}).get("quantity", 0)
    resulting_qty = quantity if override else current_qty + quantity

    # Advisory only — the real, race-proof check happens again under a
    # row lock at checkout in orders.views.order_create. This just gives
    # the customer a fast, friendly heads-up before they get that far.
    if resulting_qty > product.stock:
        return False

    cart.add(product=product, quantity=quantity, override_quantity=override)
    return True

# cart/views.py — update _add_to_cart's call site in cart_add
@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    form = CartAddProductForm(request.POST)

    if not form.is_valid():
        if request.htmx:
            return render(
                request, "catalog/_add_to_cart_widget.html", {"product": product, "state": "error"}
            )
        return redirect("cart:cart_detail")

    cd = form.cleaned_data
    success = _add_to_cart(request, product, cd["quantity"], cd["override"])

    if request.htmx:
        return render(
            request,
            "catalog/_add_to_cart_widget.html",
            {
                "product": product,
                "state": "added" if success else "error",
                "oob_cart_count": len(Cart(request)) if success else None,
            },
        )

    if not success:
        messages.error(request, f"Only {product.stock} unit(s) of '{product.name}' available.")
    return redirect("cart:cart_detail")

def cart_add_widget(request, product_id):
    """
    Renders the idle 'Add to cart' state for a single product. This is what
    the added/error states call themselves after a short delay, so a
    product card resets to normal with no page reload and no custom JS.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)
    return render(
        request, "catalog/_add_to_cart_widget.html", {"product": product, "state": "idle"}
    )


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    return redirect("cart:cart_detail")


def cart_detail(request):
    cart = Cart(request)
    for item in cart:
        item["update_quantity_form"] = CartAddProductForm(
            initial={"quantity": item["quantity"], "override": True}
        )
    return render(request, "cart/cart_detail.html", {"cart": cart})