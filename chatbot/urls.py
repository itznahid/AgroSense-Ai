"""chatbot/urls.py"""
from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("",                          views.chat_page,        name="chat"),
    path("",                          views.chat_page,        name="chat_home"),
    path("send/",                     views.send_message,     name="send_message"),
    path("session/new/",              views.new_session,      name="new_session"),
    path("session/<int:session_id>/", views.session_history,  name="session_history"),
    path("session/<int:session_id>/delete/", views.delete_session, name="delete_session"),
    path("profile/",                  views.my_profile,       name="my_profile"),
]
