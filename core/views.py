from catalog.models import Product
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render


# Create your views here.
def home_view(request):
    products = Product.objects.filter(is_active=True)
    paginator = Paginator(products, 8)
    page_number = request.GET.get("page")

    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    return render(
        request,
        "core/home.html",
        {
            "products": page_obj,
            "page_obj": page_obj,
        },
    )
