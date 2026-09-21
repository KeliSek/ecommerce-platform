# dashboard/forms.py
from catalog.models import Category, Product
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from orders.models import Order

from .utils import unique_slugify


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "description",
            "price",
            "stock",
            "image",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Save product", css_class="btn btn-primary")
        )

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data["stock"]
        if stock < 0:
            raise forms.ValidationError("Stock can't be negative.")
        return stock

    def save(self, commit=True):
        product = super().save(commit=False)
        if not product.slug:
            product.slug = unique_slugify(Product, product.name)
        if commit:
            product.save()
        return product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit("submit", "Save category", css_class="btn btn-primary")
        )

    def save(self, commit=True):
        category = super().save(commit=False)
        if not category.slug:
            category.slug = unique_slugify(Category, category.name)
        if commit:
            category.save()
        return category


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "d-flex gap-2 align-items-end"


class ProductImageUploadForm(forms.Form):
    image = forms.ImageField(
        label="Product photo",
        help_text="Upload a clear photo. AI will suggest a name, description, category, and price to review.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_tag = False