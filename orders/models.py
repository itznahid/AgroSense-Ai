import uuid

from django.db import models
from django.contrib.auth.models import User


class Order(models.Model):
    # ── Status constants ──────────────────────────────────────────────────────
    STATUS_PENDING    = 'PENDING'
    STATUS_CONFIRMED  = 'CONFIRMED'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_SHIPPED    = 'SHIPPED'
    STATUS_DELIVERED  = 'DELIVERED'
    STATUS_COMPLETED  = 'COMPLETED'
    STATUS_CANCELLED  = 'CANCELLED'
    STATUS_REJECTED   = 'REJECTED'

    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_CONFIRMED,  'Confirmed'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED,    'Shipped'),
        (STATUS_DELIVERED,  'Delivered'),
        (STATUS_COMPLETED,  'Completed'),
        (STATUS_CANCELLED,  'Cancelled'),
        (STATUS_REJECTED,   'Rejected'),
    ]

    # ── Allowed transitions ───────────────────────────────────────────────────
    MERCHANT_TRANSITIONS = {
        STATUS_PENDING:    [STATUS_CONFIRMED, STATUS_REJECTED],
        STATUS_CONFIRMED:  [STATUS_PROCESSING],
        STATUS_PROCESSING: [STATUS_SHIPPED],
        STATUS_SHIPPED:    [STATUS_DELIVERED],
    }
    CUSTOMER_TRANSITIONS = {
        STATUS_PENDING:   [STATUS_CANCELLED],
        STATUS_DELIVERED: [STATUS_COMPLETED],
    }

    # ── Fields ────────────────────────────────────────────────────────────────
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=24, unique=True, db_index=True)

    customer = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='orders',
    )
    merchant = models.ForeignKey(
        'accounts.UserAccount', on_delete=models.PROTECT,
        related_name='received_orders',
        limit_choices_to={'role': 'merchant'},
    )

    status        = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                     default=STATUS_PENDING, db_index=True)
    subtotal      = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    tax           = models.DecimalField(max_digits=8,  decimal_places=2, default=0)
    total_amount  = models.DecimalField(max_digits=12, decimal_places=2)
    notes         = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['merchant',  'status']),
        ]

    def __str__(self):
        return f"Order #{self.order_number}"

    # ── Permission helpers ────────────────────────────────────────────────────

    @property
    def is_cancellable_by_customer(self):
        return self.status == self.STATUS_PENDING

    @property
    def is_rejectable_by_merchant(self):
        return self.status == self.STATUS_PENDING

    @property
    def is_confirmable_by_customer(self):
        return self.status == self.STATUS_DELIVERED

    def merchant_next_statuses(self):
        return self.MERCHANT_TRANSITIONS.get(self.status, [])

    def customer_next_statuses(self):
        return self.CUSTOMER_TRANSITIONS.get(self.status, [])

    # ── Display helpers ───────────────────────────────────────────────────────

    STATUS_BADGE = {
        STATUS_PENDING:    ('text-amber-400',   'bg-amber-400/10',   'border-amber-400/20'),
        STATUS_CONFIRMED:  ('text-indigo-400',  'bg-indigo-400/10',  'border-indigo-400/20'),
        STATUS_PROCESSING: ('text-sky-400',     'bg-sky-400/10',     'border-sky-400/20'),
        STATUS_SHIPPED:    ('text-blue-400',    'bg-blue-400/10',    'border-blue-400/20'),
        STATUS_DELIVERED:  ('text-emerald-400', 'bg-emerald-400/10', 'border-emerald-400/20'),
        STATUS_COMPLETED:  ('text-green-400',   'bg-green-400/10',   'border-green-400/20'),
        STATUS_CANCELLED:  ('text-red-400',     'bg-red-400/10',     'border-red-400/20'),
        STATUS_REJECTED:   ('text-rose-400',    'bg-rose-400/10',    'border-rose-400/20'),
    }

    @property
    def badge_classes(self):
        parts = self.STATUS_BADGE.get(
            self.status,
            ('text-slate-400', 'bg-slate-400/10', 'border-slate-400/20'),
        )
        return ' '.join(parts)


class OrderItem(models.Model):
    order                  = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product                = models.ForeignKey(
        'marketplace.Product', on_delete=models.SET_NULL, null=True, blank=True,
    )
    product_name_snapshot  = models.CharField(max_length=200)
    product_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    quantity               = models.PositiveIntegerField()
    total_price            = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=['order'])]

    def __str__(self):
        return f"{self.quantity}× {self.product_name_snapshot}"


class ShippingAddress(models.Model):
    order        = models.OneToOneField(Order, on_delete=models.CASCADE,
                                        related_name='shipping_address')
    full_name    = models.CharField(max_length=150)
    phone        = models.CharField(max_length=25)
    district     = models.CharField(max_length=100)
    area         = models.CharField(max_length=150)
    full_address = models.TextField()

    def __str__(self):
        return f"{self.full_name} – {self.district}"


class OrderStatusHistory(models.Model):
    order           = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    previous_status = models.CharField(max_length=20, blank=True)
    new_status      = models.CharField(max_length=20)
    changed_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.order.order_number}: {self.previous_status} → {self.new_status}"


class Notification(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message    = models.TextField()
    is_read    = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"→ {self.user.username}: {self.message[:60]}"
