# cart/context_processors.py
from .cart import Cart


def cart_count(request):
    """
    Exposes the total item count in the session cart to every template, so
    the nav bar badge is correct on normal page loads. The htmx add-to-cart
    flow updates the badge live via an out-of-band swap instead of relying
    on this (no full reload happens there), but this covers everything
    else: first page load, non-JS fallback, cart page, checkout, etc.
    """
    return {"cart_count": len(Cart(request))}