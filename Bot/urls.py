from django.urls import path
from .views import SuperuserLoginView, admin_dashboard

urlpatterns = [
    path('accounts/login/', SuperuserLoginView.as_view(), name='account_login'),
    path('admin-board/', admin_dashboard, name='admin_dashboard'),
]

