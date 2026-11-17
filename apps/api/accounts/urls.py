from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("token/", views.LoginView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.MeView.as_view(), name="me"),
]
