from django.db import models
from django.contrib.auth.models import User

ROLE_USER     = 'user'
ROLE_MERCHANT = 'merchant'

ROLE_CHOICES = [
    (ROLE_USER,     'User'),
    (ROLE_MERCHANT, 'Merchant'),
]


class UserAccount(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account')
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    phone      = models.CharField(max_length=25, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_merchant(self):
        return self.role == ROLE_MERCHANT

    @property
    def is_regular_user(self):
        return self.role == ROLE_USER

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class MerchantProfile(models.Model):
    """One-to-one Shop for each Merchant account."""
    account          = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name='merchant_profile')
    shop_name        = models.CharField(max_length=200)
    shop_description = models.TextField(blank=True)
    shop_icon        = models.CharField(max_length=10, default='🏪')
    # ── NEW: logo image upload ────────────────────────────────────────────────
    logo             = models.ImageField(upload_to='shop_logos/', null=True, blank=True)
    is_verified      = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.shop_name
