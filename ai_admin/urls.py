"""ai_admin/urls.py"""
from django.urls import path
from . import views

app_name = "ai_admin"

urlpatterns = [
    path("",                    views.dashboard,    name="dashboard"),
    path("keys/",               views.keys_list,    name="keys_list"),
    path("keys/add/",           views.key_add,      name="key_add"),
    path("keys/<int:pk>/edit/", views.key_edit,     name="key_edit"),
    path("keys/<int:pk>/delete/",views.key_delete,  name="key_delete"),
    path("keys/<int:pk>/toggle/",views.key_toggle,  name="key_toggle"),
    path("keys/<int:pk>/test/", views.key_test,     name="key_test"),
    path("keys/reorder/",       views.key_reorder,  name="key_reorder"),
    path("api/live-stats/",     views.live_stats,   name="live_stats"),
]
