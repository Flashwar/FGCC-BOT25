from django.urls import path

from .views import SuperuserLoginView, admin_dashboard, customer_stats, customer_stats_pdf, messages, webchat, \
    get_directline_token

urlpatterns = [

    # Login Endpoint, from ReAuth
    path('', SuperuserLoginView.as_view(), name='account_login'),

    # Admin dashboard
    path('adminboard/', admin_dashboard, name='admin_dashboard'),

    # Statistics
    path('statistics/', customer_stats, name='statistics'),

    # download Endpoint for the statistics (pdf)
    path('adminboard/statistics/pdf/<str:chart_type>/', customer_stats_pdf, name='customer_stats_pdf'),

    # webchat Endpoint with the corresponding function
    path('webchat/', webchat, name='webchat'),

    # API WebChat Token Endpoint
    path('api/webchat/token/', get_directline_token, name='webchat_token'),

    # bot Endpoint
    path('api/messages/', messages, name='bot_messages'),



]
