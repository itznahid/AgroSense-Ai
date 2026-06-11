from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [

    # ── Customer: checkout ────────────────────────────────────────────────────
    path('checkout/',                            views.checkout_view,     name='checkout'),

    # ── Customer: order history ───────────────────────────────────────────────
    path('my-orders/',                           views.my_orders,         name='my_orders'),
    path('my-orders/<uuid:order_id>/',           views.order_detail,      name='order_detail'),
    path('my-orders/<uuid:order_id>/cancel/',    views.cancel_order,      name='cancel_order'),
    path('my-orders/<uuid:order_id>/confirm/',   views.confirm_delivery,  name='confirm_delivery'),

    # ── Merchant: order management ────────────────────────────────────────────
    path('merchant/orders/',                              views.merchant_order_list,      name='merchant_order_list'),
    path('merchant/orders/pending/',                      views.merchant_pending_orders,  name='pending_orders'),
    path('merchant/orders/active/',                       views.merchant_confirmed_orders,name='confirmed_orders'),
    path('merchant/orders/<uuid:order_id>/',              views.merchant_order_detail,    name='merchant_order_detail'),
    path('merchant/orders/<uuid:order_id>/accept/',       views.accept_order,             name='accept_order'),
    path('merchant/orders/<uuid:order_id>/reject/',       views.reject_order,             name='reject_order'),
    path('merchant/orders/<uuid:order_id>/process/',      views.mark_processing,          name='mark_processing'),
    path('merchant/orders/<uuid:order_id>/ship/',         views.mark_shipped,             name='mark_shipped'),
    path('merchant/orders/<uuid:order_id>/deliver/',      views.mark_delivered,           name='mark_delivered'),

    # ── Notifications ─────────────────────────────────────────────────────────
    path('notifications/',                               views.notification_list,        name='notifications'),
    path('notifications/<int:notif_id>/read/',           views.mark_notification_read,   name='mark_notification_read'),
]
