from catalog.models import Category, Product
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import F
from django.shortcuts import render


# Create your views here.
def home_view(request):
    # Featured products - get first 4 active products
    featured_products = Product.objects.filter(is_active=True)[:4]
    
    # Collection products - one per category, ordered by category
    categories = Category.objects.all()
    collection_products = []
    for category in categories:
        product = Product.objects.filter(
            category=category, is_active=True
        ).first()
        if product:
            collection_products.append(product)

    return render(
        request,
        "core/home.html",
        {
            "featured_products": featured_products,
            "collection_products": collection_products,
        },
    )
