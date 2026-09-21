# dashboard/views.py
import logging

from catalog.models import Category, Product
from django.conf import settings
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from orders.models import Order, OrderStatusHistory
from payments.models import Payment

from .ai import AIAnalysisError, analyze_product_image
from .decorators import vendor_required
from .forms import CategoryForm, OrderStatusForm, ProductForm, ProductImageUploadForm
from .utils import unique_slugify

logger = logging.getLogger(__name__)


@vendor_required
def dashboard_index(request):
    revenue = (
        Payment.objects.filter(status="success").aggregate(total=Sum("amount"))["total"] or 0
    )
    context = {
        "total_products": Product.objects.count(),
        "low_stock_count": Product.objects.filter(
            stock__lte=settings.LOW_STOCK_THRESHOLD, is_active=True
        ).count(),
        "total_orders": Order.objects.count(),
        "pending_orders": Order.objects.filter(status="pending").count(),
        "revenue": revenue,
        "recent_orders": Order.objects.select_related("user").order_by("-created_at")[:5],
    }
    return render(request, "dashboard/index.html", context)


# ---- Products ----

@vendor_required
def product_list(request):
    products = Product.objects.select_related("category").order_by("-created_at")

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    category_slug = request.GET.get("category")
    if category_slug:
        products = products.filter(category__slug=category_slug)

    paginator = Paginator(products, 15)
    try:
        page_obj = paginator.get_page(request.GET.get("page"))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    return render(
        request,
        "dashboard/product_list.html",
        {
            "page_obj": page_obj,
            "categories": Category.objects.all(),
            "query": query,
            "low_stock_threshold": settings.LOW_STOCK_THRESHOLD,
        },
    )


@vendor_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"'{product.name}' was created.")
            return redirect("dashboard:product_list")
    else:
        form = ProductForm()
    return render(request, "dashboard/product_form.html", {"form": form, "is_create": True})


@vendor_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{product.name}' was updated.")
            return redirect("dashboard:product_list")
    else:
        form = ProductForm(instance=product)
    return render(
        request, "dashboard/product_form.html", {"form": form, "is_create": False, "product": product}
    )


@vendor_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    product.delete()
    messages.success(request, f"'{name}' was deleted.")
    return redirect("dashboard:product_list")


@vendor_required
def product_ai_upload(request):
    if request.method == "POST":
        form = ProductImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = form.cleaned_data["image"]
            image_bytes = image_file.read()
            image_file.seek(0)  # rewind so Django can still save it to storage

            suggestion = None
            try:
                suggestion = analyze_product_image(image_bytes, image_file.content_type)
            except AIAnalysisError as exc:
                logger.warning("AI product analysis failed: %s", exc)
                if settings.DEBUG:
                    messages.warning(request, f"AI analysis failed: {exc}")
                else:
                    messages.warning(
                        request,
                        "AI analysis didn't work this time, so a draft was created with "
                        "the photo only — fill in the details manually below.",
                    )

            category = None
            if suggestion and suggestion["category_guess"]:
                category = Category.objects.filter(
                    name__iexact=suggestion["category_guess"]
                ).first()

            product = Product(
                name=suggestion["name"] if suggestion else "New product (untitled)",
                description=suggestion["description"] if suggestion else "",
                price=(suggestion["price_ghs"] if suggestion and suggestion["price_ghs"] else 0),
                stock=0,
                category=category,
                image=image_file,
                is_active=False,
            )
            product.slug = unique_slugify(Product, product.name)
            product.save()

            if suggestion:
                messages.success(
                    request,
                    "AI generated a draft listing — review every field, especially "
                    "the price, then tick Active when it's ready to go live.",
                )
            return redirect("dashboard:product_update", pk=product.pk)
    else:
        form = ProductImageUploadForm()

    return render(request, "dashboard/product_ai_upload.html", {"form": form})


# ---- Categories ----

@vendor_required
def category_list(request):
    categories = Category.objects.all().order_by("name")
    return render(request, "dashboard/category_list.html", {"categories": categories})


@vendor_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
            return redirect("dashboard:category_list")
    else:
        form = CategoryForm()
    return render(request, "dashboard/category_form.html", {"form": form, "is_create": True})


@vendor_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect("dashboard:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(
        request, "dashboard/category_form.html", {"form": form, "is_create": False, "category": category}
    )


@vendor_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.products.exists():
        messages.error(
            request,
            f"Can't delete '{category.name}' — it still has products assigned. "
            "Reassign or delete those products first.",
        )
        return redirect("dashboard:category_list")
    name = category.name
    category.delete()
    messages.success(request, f"Category '{name}' was deleted.")
    return redirect("dashboard:category_list")


# ---- Orders ----

@vendor_required
def order_list(request):
    orders = Order.objects.select_related("user").order_by("-created_at")

    query = request.GET.get("q", "").strip()
    if query:
        orders = orders.filter(order_number__icontains=query)

    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)

    paginator = Paginator(orders, 20)
    try:
        page_obj = paginator.get_page(request.GET.get("page"))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    return render(
        request,
        "dashboard/order_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "status": status,
            "status_choices": Order.STATUS_CHOICES,
        },
    )


@vendor_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__product"), pk=pk
    )
    status_form = OrderStatusForm(instance=order)
    return render(request, "dashboard/order_detail.html", {"order": order, "status_form": status_form})


@vendor_required
@require_POST
def order_update_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    old_status = order.status  # captured before form.is_valid() mutates the in-memory instance
    form = OrderStatusForm(request.POST, instance=order)
    if form.is_valid():
        new_status = form.cleaned_data["status"]
        if new_status != old_status:
            form.save()
            OrderStatusHistory.objects.create(
                order=order,
                previous_status=old_status,
                new_status=new_status,
                changed_by=request.user,
            )
        if request.htmx:
            return render(
                request,
                "dashboard/_order_status_panel.html",
                {"order": order, "status_form": OrderStatusForm(instance=order)},
            )
        messages.success(
            request, f"Order {order.order_number} marked as {order.get_status_display()}."
        )
    else:
        if request.htmx:
            return render(
                request,
                "dashboard/_order_status_panel.html",
                {"order": order, "status_form": form},
            )
        messages.error(request, "Could not update order status.")
    return redirect("dashboard:order_detail", pk=pk)