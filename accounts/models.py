from django.contrib.auth.models import AbstractUser
from django.db import models


# Create your models here.
class User(AbstractUser):
    phone_number = models.CharField(max_length=20, blank=True)
    is_customer = models.BooleanField(default=True)
    is_vendor_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.username
