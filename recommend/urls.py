from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('',                 views.home,         name='home'),
    path('features/',        views.features,     name='features'),

    # Protected — general
    path('dashboard/',       views.dashboard,    name='dashboard'),
    path('profile/',         views.profile_view, name='profile'),

    # Protected — ML
    path('predict/',         views.predict_view, name='predict'),
    path('predict/weather/', views.weather_view, name='weather_api'),
    path('history/',         views.history_view, name='history'),
]