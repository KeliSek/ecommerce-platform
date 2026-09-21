# catalog/views.py
from cart.forms import CartAddProductForm
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product


def product_list(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()

    category_slug = request.GET.get("category")
    if category_slug:
        products = products.filter(category__slug=category_slug)

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    return render(
        request,
        "catalog/product_list.html",
        {
            "products": products,
            "categories": categories,
            "query": query,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    cart_product_form = CartAddProductForm()
    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "cart_product_form": cart_product_form,
        },
    )