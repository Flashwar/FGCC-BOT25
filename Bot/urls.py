from django.urls import path

from . import emu_views, telegram_views
from .views import SuperuserLoginView, admin_dashboard, customer_stats, customer_stats_pdf, messages
urlpatterns = [
    path('', SuperuserLoginView.as_view(), name='account_login'),
    path('adminboard/', admin_dashboard, name='admin_dashboard'),
    path('statistics/', customer_stats, name='statistics'),
    path('adminboard/statistics/pdf/<str:chart_type>/', customer_stats_pdf, name='customer_stats_pdf'),

#     path('api/messages/', messages, name='bot_messages'),
#     # Call endpoint
#     path('api/calls/', calls, name='calls'),
#
#     # Audio Processing endpoint
#     path('api/audio/input/', incoming_call, name='audio_input'),
#     path('api/audio/output/', call_callback, name='audio_output'),
#     path('api/media/stream/', media_stream, name='media_stream'),

    path('api/messages/', messages, name='bot_messages'),

    path('emulator/test/', emu_views.emulator_test, name='emulator_bot_test'),
    path('emulator/messages/', emu_views.emulator_messages, name='emulator_bot_messages'),

path('telegram/test/', telegram_views.telegram_test, name='telegram_bot_test'),
    path('telegram/messages/', telegram_views.telegram_messages, name='telegram_bot_messages'),

]

