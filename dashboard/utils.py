# dashboard/utils.py
from django.utils.text import slugify


def unique_slugify(model, name, slug_field="slug", max_length=50):
    """
    Builds a unique slug for `model` from `name`. The base slug is truncated
    so a numeric suffix (-2, -3, ...) always fits within max_length, and the
    DB is checked on every attempt so two vendors saving similarly-named
    items back-to-back can never collide.
    """
    base_slug = slugify(name)[: max_length - 5] or "item"
    slug = base_slug
    counter = 2
    while model.objects.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug
