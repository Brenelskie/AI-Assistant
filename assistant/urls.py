from django.urls import path

from . import views


app_name = "assistant"
urlpatterns = [
    path("", views.home, name="home"),
    path("api/csrf/", views.csrf_token, name="csrf_token"),
    path("api/ask/", views.ask, name="ask"),
]
