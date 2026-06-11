"""
orders/signals.py
=================
Signal receivers for the orders app.

Business-critical notification logic lives in services.py (called inline
within transactions).  Signals here are for *side effects* that should
run after a commit — e.g., triggering external webhooks, emails, or
third-party integrations — without blocking the main transaction.

To add email sending:
    1. pip install django-anymail (or configure Django's email backend)
    2. Uncomment the email block below and fill in your templates.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def order_post_save(sender, instance: Order, created: bool, **kwargs):
    """
    Fired after every Order save.  Runs outside the service transaction
    (post_save fires after commit when using on_commit-safe patterns).
    """
    if created:
        logger.info(
            "New order created: %s  customer=%s  merchant=%s  total=%.2f",
            instance.order_number,
            instance.customer_id,
            instance.merchant_id,
            instance.total_amount,
        )
    else:
        logger.info(
            "Order updated: %s  status=%s",
            instance.order_number,
            instance.status,
        )

    # ── Uncomment to send order-confirmed email ───────────────────────────
    # if not created and instance.status == Order.STATUS_CONFIRMED:
    #     from django.core.mail import send_mail
    #     send_mail(
    #         subject=f"Your order #{instance.order_number} is confirmed!",
    #         message=f"Hi {instance.customer.first_name}, your order has been confirmed.",
    #         from_email="noreply@agrosense.app",
    #         recipient_list=[instance.customer.email],
    #         fail_silently=True,
    #     )
