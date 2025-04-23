from django.urls import path
from .views import SuperuserLoginView, admin_dashboard, customer_stats, customer_stats_pdf

urlpatterns = [
    path('', SuperuserLoginView.as_view(), name='account_login'),
    path('adminboard/', admin_dashboard, name='admin_dashboard'),
    path('statistics/', customer_stats, name='statistics'),
path('adminboard/statistics/pdf/<str:chart_type>/', customer_stats_pdf, name='customer_stats_pdf'),
]

