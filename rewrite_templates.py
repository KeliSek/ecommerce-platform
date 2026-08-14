from pathlib import Path

cart_template = """{% extends 'core/base.html' %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container-fluid py-5">
    <div class="container">
        <div class="d-flex flex-column flex-md-row align-items-start justify-content-between gap-3 mb-4">
            <div>
                <h1 class="h2 mb-2">Your Cart</h1>
                <p class="text-muted mb-0">Review items, update quantities, or remove products before checkout.</p>
            </div>
            {% if cart|length > 0 %}
            <div class="text-md-end">
                <span class="badge bg-primary fs-6">{{ cart|length }} items</span>
                <span class="badge bg-secondary fs-6 ms-2">${{ cart.get_total_price }}</span>
            </div>
            {% endif %}
        </div>

        {% if cart|length == 0 %}
        <div class="card shadow border-0">
            <div class="card-body text-center py-5">
                <h2 class="h4 mb-3">Your cart is empty</h2>
                <p class="text-muted mb-4">Browse our store and add products you love.</p>
                <a href="{% url 'catalog:product_list' %}" class="btn btn-primary">Shop Products</a>
            </div>
        </div>
        {% else %}
        <div class="row g-4">
            <div class="col-lg-8">
                <div class="card shadow border-0">
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table align-middle mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>Product</th>
                                        <th>Price</th>
                                        <th>Quantity</th>
                                        <th>Total</th>
                                        <th></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for item in cart %}
                                    <tr>
                                        <td>
                                            <div class="d-flex align-items-center gap-3">
                                                {% if item.product.image %}
                                                <img src="{{ item.product.image.url }}" alt="{{ item.product.name }}" class="rounded" style="width: 80px; height: 80px; object-fit: cover;">
                                                {% else %}
                                                <div class="bg-secondary bg-opacity-10 rounded d-flex align-items-center justify-content-center" style="width: 80px; height: 80px;">
                                                    <span class="text-muted small">No image</span>
                                                </div>
                                                {% endif %}
                                                <div>
                                                    <a href="{% url 'catalog:product_detail' item.product.slug %}" class="text-decoration-none fw-semibold text-dark">{{ item.product.name }}</a>
                                                    {% if not item.product.in_stock %}
                                                    <div class="small text-danger">Out of stock</div>
                                                    {% endif %}
                                                </div>
                                            </div>
                                        </td>
                                        <td class="fw-semibold">${{ item.price }}</td>
                                        <td>
                                            <form action="{% url 'cart:cart_add' item.product.id %}" method="post" class="d-flex align-items-center gap-2">
                                                {% csrf_token %}
                                                {{ item.update_quantity_form.quantity }}
                                                {{ item.update_quantity_form.override }}
                                                <button type="submit" class="btn btn-sm btn-outline-secondary">Update</button>
                                            </form>
                                        </td>
                                        <td class="fw-semibold">${{ item.total_price }}</td>
                                        <td>
                                            <form action="{% url 'cart:cart_remove' item.product.id %}" method="post">
                                                {% csrf_token %}
                                                <button type="submit" class="btn btn-sm btn-danger">Remove</button>
                                            </form>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card shadow border-0">
                    <div class="card-body">
                        <h2 class="h5 mb-3">Order Summary</h2>
                        <dl class="row mb-4">
                            <dt class="col-6 text-muted">Items</dt>
                            <dd class="col-6 text-end">{{ cart|length }}</dd>
                            <dt class="col-6 text-muted">Subtotal</dt>
                            <dd class="col-6 text-end fw-semibold">${{ cart.get_total_price }}</dd>
                        </dl>
                        <a href="{% url 'catalog:product_list' %}" class="btn btn-outline-secondary w-100 mb-2">Continue Shopping</a>
                        <a href="#" class="btn btn-primary w-100">Checkout</a>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
"""

product_template = """{% extends 'core/base.html' %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container-fluid py-5">
    <div class="container">
        <div class="row g-4">
            <div class="col-lg-6">
                <div class="card shadow border-0 overflow-hidden">
                    {% if product.image %}
                    <img src="{{ product.image.url }}" alt="{{ product.name }}" class="img-fluid w-100 object-fit-cover" style="min-height: 420px;">
                    {% else %}
                    <div class="bg-secondary bg-opacity-10 d-flex align-items-center justify-content-center" style="min-height: 420px;">
                        <span class="text-muted">No image available</span>
                    </div>
                    {% endif %}
                </div>
            </div>
            <div class="col-lg-6">
                <div class="card shadow border-0 h-100">
                    <div class="card-body d-flex flex-column gap-4">
                        <div>
                            <a href="{% url 'catalog:product_list' %}" class="text-decoration-none text-secondary">
                                <i class="bi bi-chevron-left"></i> Back to products
                            </a>
                        </div>
                        <div>
                            <h1 class="h2 mb-2">{{ product.name }}</h1>
                            <div class="d-flex flex-wrap gap-2 align-items-center mb-3">
                                <span class="h3 mb-0">${{ product.price }}</span>
                                {% if product.in_stock %}
                                <span class="badge bg-success">In stock</span>
                                {% else %}
                                <span class="badge bg-danger">Out of stock</span>
                                {% endif %}
                            </div>
                        </div>
                        <p class="text-muted">{{ product.description }}</p>
                        {% if product.in_stock %}
                        <form action="{% url 'cart:cart_add' product.id %}" method="post" class="d-flex flex-column flex-sm-row align-items-start align-items-sm-end gap-3">
                            {% csrf_token %}
                            <div class="w-100 w-sm-auto">
                                {{ cart_product_form.quantity }}
                            </div>
                            <button type="submit" class="btn btn-primary px-4">Add to Cart</button>
                        </form>
                        {% else %}
                        <div class="alert alert-danger py-2">This product is currently out of stock.</div>
                        {% endif %}
                        <div class="mt-auto pt-4">
                            <a href="{% url 'cart:cart_detail' %}" class="btn btn-outline-secondary">View Cart</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

Path(r"cart\templates\cart\cart_detail.html").write_text(
    cart_template, encoding="utf-8"
)
Path(r"catalog\templates\catalog\product_detail.html").write_text(
    product_template, encoding="utf-8"
)
print("templates updated")
