import base64
import io
from allauth.account.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http.response import HttpResponse
from django.template.loader import render_to_string
from django_tables2 import RequestConfig
from django_tables2.export import TableExport
from plotly.offline import plot
from django.shortcuts import render
from weasyprint import HTML
import plotly.io as pio
from .services import CustomerService
from Bot.website.statistics import Statistics
from injector import inject
from Bot.website.filters import CustomerFilter
from Bot.website.tables import CustomerTable

class SuperuserLoginView(LoginView):
    def form_valid(self, form):
        user = form.user
        if not user.is_superuser:
            messages.error(self.request, "Nur für Superuser.")
            return self.form_invalid(form)
        return super().form_valid(form)


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)


@superuser_required
@inject
def admin_dashboard(request, customer_service: CustomerService):
    queryset = customer_service.get_all_customers_with_relations()
    f = CustomerFilter(request.GET, queryset=queryset)
    table = CustomerTable(f.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    export_format = request.GET.get('_export', None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response(f"CustomerTable.{export_format}")

    return render(request, 'dashboard.html', {'table': table, 'filter': f})

@superuser_required
@inject
def customer_stats(request, statistics: Statistics):

    total_customers = statistics.get_total_customers()

    # Titel Chart
    title_fig = statistics.get_title_chart()
    title_chart = plot(title_fig, output_type='div', include_plotlyjs=False)
    request.session['title_fig'] = title_fig.to_json()

    # Geschlecht Chart
    gender_fig = statistics.get_gender_chart()
    gender_chart = plot(gender_fig, output_type='div', include_plotlyjs=False)
    request.session['gender_fig'] = gender_fig.to_json()

    # Land Chart
    country_fig = statistics.get_country_chart()
    country_chart = plot(country_fig, output_type='div', include_plotlyjs=False)
    request.session['country_fig'] = country_fig.to_json()

    # Alter Chart
    age_fig = statistics.get_age_chart()
    age_chart = plot(age_fig, output_type='div', include_plotlyjs=False)
    request.session['age_fig'] = age_fig.to_json()

    return render(request, 'statistics.html', {
        'total_customers': total_customers,
        'title_chart': title_chart,
        'gender_chart': gender_chart,
        'country_chart': country_chart,
        'age_chart': age_chart
    })

def generate_pdf_from_plotly(fig, title, filename, total_customers):
    # Export Plotly figure to PNG
    img_bytes = io.BytesIO()
    fig.write_image(img_bytes, format='png', width=800, height=500)
    img_bytes.seek(0)

    # Convert PNG to base64
    encoded = base64.b64encode(img_bytes.read()).decode()
    image_uri = f'data:image/png;base64,{encoded}'

    # Render HTML
    html_string = render_to_string('pdf_stats_template.html', {
        'title': title,
        'image_uri': image_uri,
        'total_customers': total_customers
    })

    # Generate PDF
    pdf = HTML(string=html_string).write_pdf()
    return HttpResponse(pdf, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })

def generate_pdf_from_charts(chart_data, total_customers):
    charts = []
    for title, fig in chart_data:
        image_bytes = pio.to_image(fig, format="png", width=800, height=500)
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        charts.append({
            "title": title,
            "image_base64": base64_image
        })

    html_string = render_to_string('pdf_stats_template.html', {
        'charts': charts,
        'total_customers': total_customers,
    })

    pdf = HTML(string=html_string).write_pdf()
    return HttpResponse(
        pdf,
        content_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename="kunden_statistiken_gesamt.pdf"'}
    )

@inject
def customer_stats_pdf(request, chart_type: str, statistics: Statistics, customer_service: CustomerService):
    total_customers = customer_service.get_total_count()
    chart_data = [
        ("Titelverteilung", statistics.get_title_chart()),
        ("Geschlechterverteilung", statistics.get_gender_chart()),
        ("Kunden pro Land", statistics.get_country_chart()),
        ("Altersverteilung", statistics.get_age_chart()),
    ]

    match chart_type:
        case "title":
            return generate_pdf_from_plotly(
                statistics.get_title_chart(), "Titelverteilung", "titel_statistik.pdf", total_customers
            )
        case "gender":
            return generate_pdf_from_plotly(
                statistics.get_gender_chart(), "Geschlechterverteilung", "geschlecht_statistik.pdf", total_customers
            )
        case "country":
            return generate_pdf_from_plotly(
                statistics.get_country_chart(), "Kunden pro Land", "land_statistik.pdf", total_customers
            )
        case "age":
            return generate_pdf_from_plotly(
                statistics.get_age_chart(), "Altersverteilung", "alters_statistik.pdf", total_customers
            )
        case "all":
            return generate_pdf_from_charts(chart_data, total_customers)
        case _:
            return HttpResponse("Ungültiger Chart-Typ", status=400)


# import sys
# import json
# from http import HTTPStatus
#
# from django.views.decorators.csrf import csrf_exempt
# from django.http import HttpResponse
#
# # Bot Framework Core Imports
# from botbuilder.core import (
#     BotFrameworkAdapter,
#     BotFrameworkAdapterSettings,
#     TurnContext,
#     ConversationState,
#     UserState,
#     MemoryStorage  # WICHTIG: Ersetze dies in Produktion!
# )
# from botbuilder.schema import Activity, ActivityTypes
#
# # Importiere deinen Bot (angenommen, er liegt in 'bot_app/message_bot.py')
# from .message_bot import RegistrationTextBot
#
# # Bot Framework Adapter Einstellungen
# # In Produktion sollten APP_ID und APP_PASSWORD aus Umgebungsvariablen geladen werden.
# # Für lokale Tests kannst du sie leer lassen oder Placeholder verwenden.
# APP_ID = ""  # Ersetze dies mit deiner Microsoft App ID
# APP_PASSWORD = ""  # Ersetze dies mit deinem Microsoft App Password
#
# # Erstelle den Bot Framework Adapter
# SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
# ADAPTER = BotFrameworkAdapter(SETTINGS)
#
# # Speicher für den Zustand.
# # ACHTUNG: MemoryStorage ist NICHT für die Produktion geeignet,
# # da Daten bei jedem Neustart des Servers verloren gehen!
# # Für die Produktion solltest du AzureBlobStorage, CosmosDbStorage etc. verwenden.
# MEMORY = MemoryStorage()
# CONVERSATION_STATE = ConversationState(MEMORY)
# USER_STATE = UserState(MEMORY)
#
# # Erstelle eine Instanz deines Bots
# # Übergib die Zustands-Manager an den Bot
# BOT = RegistrationTextBot(CONVERSATION_STATE, USER_STATE)
#
#
# # Fehlermanagement für den Adapter
# async def on_error(context: TurnContext, error: Exception):
#     # Dies wird aufgerufen, wenn ein Fehler während der Bot-Verarbeitung auftritt.
#     print(f"\n [on_error] Unbehandelter Fehler: {error}", file=sys.stderr)
#     await context.send_activity("Entschuldigung, es ist ein Fehler aufgetreten und der Bot muss neu starten.")
#
#     # Optional: Den Zustand löschen, um den Bot zurückzusetzen, wenn ein Fehler auftritt
#     await CONVERSATION_STATE.delete(context)
#     await USER_STATE.delete(context)
#
#
# # Registriere den Fehlerhandler beim Adapter
# ADAPTER.on_turn_error = on_error
#
#
# @csrf_exempt
# async def messages(request):
#     """
#     Diese Django-View empfängt eingehende HTTP-POST-Anfragen vom Bot Framework Connector.
#     """
#     if request.method != 'POST':
#         return HttpResponse(status=HTTPStatus.METHOD_NOT_ALLOWED)
#
#     # Überprüfe den Content-Type des Requests
#     if "application/json" not in request.headers.get("Content-Type", ""):
#         return HttpResponse(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
#
#     # Lese den Request-Body und deserialisiere ihn in ein Activity-Objekt
#     body = request.body.decode('utf-8')
#     activity = Activity().deserialize(json.loads(body))
#
#     # Hole den Authorization-Header (wichtig für die Authentifizierung bei Azure Bot Service)
#     auth_header = request.headers.get("Authorization", "")
#
#     try:
#         # Der Adapter verarbeitet die eingehende Aktivität und ruft die Bot-Logik auf.
#         # Die Methode BOT.on_turn wird pro eingehender Aktivität aufgerufen.
#         await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
#         return HttpResponse(status=HTTPStatus.OK)
#
#     except Exception as e:
#         # Fange jegliche Fehler ab, die vor oder während der Adapter-Verarbeitung auftreten könnten.
#         print(f"Fehler bei der Verarbeitung der Bot-Aktivität: {e}", file=sys.stderr)
#         return HttpResponse(status=HTTPStatus.INTERNAL_SERVER_ERROR, text=str(e))
#
# import sys
# import json
# from http import HTTPStatus
#
# from django.views.decorators.csrf import csrf_exempt
# from django.http import HttpResponse, JsonResponse
# from django.conf import settings
#
# # Bot Framework Core Imports
# from botbuilder.core import (
#     BotFrameworkAdapter,
#     BotFrameworkAdapterSettings,
#     TurnContext,
#     ConversationState,
#     UserState,
#     MemoryStorage
# )
# from botbuilder.schema import Activity
#
# # Importiere den Unified Bot
# from call_bot import UnifiedTeamsBot
#
# # Bot Framework Adapter Einstellungen
# APP_ID = getattr(settings, 'MICROSOFT_APP_ID', "")
# APP_PASSWORD = getattr(settings, 'MICROSOFT_APP_PASSWORD', "")
#
# print(f"🤖 Bot Konfiguration - App ID: {APP_ID[:8] if APP_ID else 'Nicht gesetzt'}...")
#
# # Erstelle den Bot Framework Adapter
# SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
# ADAPTER = BotFrameworkAdapter(SETTINGS)
#
# # Speicher für den Zustand
# # WARNUNG: MemoryStorage ist NICHT für Produktion geeignet!
# # Verwende für Produktion AzureBlobStorage oder CosmosDbStorage
# MEMORY = MemoryStorage()
# CONVERSATION_STATE = ConversationState(MEMORY)
# USER_STATE = UserState(MEMORY)
#
# # Erstelle eine Instanz des Unified Bots
# BOT = UnifiedTeamsBot(CONVERSATION_STATE, USER_STATE)
#
# print("✅ Unified Teams Bot erfolgreich initialisiert")
#
#
# # Fehlermanagement für den Adapter
# async def on_error(context: TurnContext, error: Exception):
#     """Behandelt Fehler im Bot Framework"""
#     print(f"\n❌ [Bot Error] {error}", file=sys.stderr)
#
#     try:
#         # Bestimme ob es ein Call oder Chat ist
#         is_call = BOT._is_call_context(context)
#
#         if is_call:
#             # Für Anrufe: Sprachausgabe
#             await BOT._speak_to_caller(context, "Entschuldigung, es ist ein technischer Fehler aufgetreten.")
#         else:
#             # Für Chat: Text-Nachricht
#             await context.send_activity("Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.")
#
#     except Exception as send_error:
#         print(f"❌ Fehler beim Senden der Fehlernachricht: {send_error}", file=sys.stderr)
#
#     # Zustand zurücksetzen bei kritischen Fehlern
#     try:
#         await CONVERSATION_STATE.delete(context)
#         await USER_STATE.delete(context)
#     except Exception as cleanup_error:
#         print(f"❌ Fehler beim Zustand-Cleanup: {cleanup_error}", file=sys.stderr)
#
#
# # Registriere den Fehlerhandler
# ADAPTER.on_turn_error = on_error
#
#
# @csrf_exempt
# async def messages(request):
#     """
#     Haupt-Endpoint für Bot Framework Nachrichten
#     Behandelt sowohl Text-Chat als auch Teams-Nachrichten
#     """
#     if request.method != 'POST':
#         return HttpResponse("Nur POST erlaubt", status=HTTPStatus.METHOD_NOT_ALLOWED)
#
#     content_type = request.headers.get("Content-Type", "")
#     if "application/json" not in content_type:
#         return HttpResponse("Content-Type muss application/json sein", status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
#
#     try:
#         # Request Body deserialisieren
#         body = request.body.decode('utf-8')
#         activity = Activity().deserialize(json.loads(body))
#         auth_header = request.headers.get("Authorization", "")
#
#         # Logge wichtige Informationen
#         print(f"📨 Aktivität empfangen: {activity.type} von {activity.channel_id}")
#         if hasattr(activity, 'text') and activity.text:
#             print(f"📝 Text: {activity.text[:100]}...")
#         if hasattr(activity, 'name') and activity.name:
#             print(f"🔔 Event Name: {activity.name}")
#
#         # Verarbeite die Aktivität mit dem Unified Bot
#         await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
#
#         return HttpResponse("OK", status=HTTPStatus.OK)
#
#     except json.JSONDecodeError as e:
#         print(f"❌ JSON Decode Fehler: {e}", file=sys.stderr)
#         return HttpResponse("Ungültiges JSON", status=HTTPStatus.BAD_REQUEST)
#
#     except Exception as e:
#         print(f"❌ Fehler bei der Aktivitätsverarbeitung: {e}", file=sys.stderr)
#         import traceback
#         traceback.print_exc()
#         return HttpResponse("Interner Server Fehler", status=HTTPStatus.INTERNAL_SERVER_ERROR)
#
#
# @csrf_exempt
# async def calls(request):
#     """
#     Spezieller Endpoint für Microsoft Teams Call Events
#     Behandelt Anruf-spezifische Aktivitäten wie Invite, Established, Terminated
#     """
#     if request.method != 'POST':
#         return HttpResponse("Nur POST erlaubt", status=HTTPStatus.METHOD_NOT_ALLOWED)
#
#     content_type = request.headers.get("Content-Type", "")
#     if "application/json" not in content_type:
#         return HttpResponse("Content-Type muss application/json sein", status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
#
#     try:
#         # Request Body deserialisieren
#         body = request.body.decode('utf-8')
#         activity = Activity().deserialize(json.loads(body))
#         auth_header = request.headers.get("Authorization", "")
#
#         # Logge Call-spezifische Informationen
#         print(f"📞 Call-Aktivität empfangen: {activity.type}")
#         if hasattr(activity, 'name'):
#             print(f"📞 Call Event Name: {activity.name}")
#         if hasattr(activity, 'value') and activity.value:
#             print(f"📞 Call Value: {activity.value}")
#
#         # Verarbeite mit dem Unified Bot (erkennt automatisch Call-Kontext)
#         await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
#
#         return HttpResponse("OK", status=HTTPStatus.OK)
#
#     except json.JSONDecodeError as e:
#         print(f"❌ JSON Decode Fehler bei Call: {e}", file=sys.stderr)
#         return HttpResponse("Ungültiges JSON", status=HTTPStatus.BAD_REQUEST)
#
#     except Exception as e:
#         print(f"❌ Fehler bei Call-Verarbeitung: {e}", file=sys.stderr)
#         import traceback
#         traceback.print_exc()
#         return HttpResponse("Interner Server Fehler", status=HTTPStatus.INTERNAL_SERVER_ERROR)
#
#
# @csrf_exempt
# async def incoming_call(request):
#     """
#     Endpoint für eingehende Anrufe von Teams
#     Behandelt das initiale Call Invite
#     """
#     if request.method != 'POST':
#         return HttpResponse("Nur POST erlaubt", status=HTTPStatus.METHOD_NOT_ALLOWED)
#
#     try:
#         body = request.body.decode('utf-8')
#         call_data = json.loads(body)
#
#         print(f"📞 Eingehender Anruf: {call_data}")
#
#         # Automatische Annahme-Antwort
#         response_data = {
#             "action": "accept",
#             "callbackUri": f"{getattr(settings, 'BOT_BASE_URL', '')}/bot/api/call_callback",
#             "acceptedModalities": ["audio"],
#             "mediaConfig": {
#                 "removeFromDefaultAudioGroup": False
#             }
#         }
#
#         return JsonResponse(response_data)
#
#     except Exception as e:
#         print(f"❌ Fehler bei eingehendem Anruf: {e}", file=sys.stderr)
#         return JsonResponse({
#             "error": "Fehler bei Anrufverarbeitung"
#         }, status=HTTPStatus.INTERNAL_SERVER_ERROR)
#
#
# @csrf_exempt
# async def call_callback(request):
#     """
#     Callback-Endpoint für Call Status Updates
#     Teams ruft diesen Endpoint für Call-Status-Änderungen auf
#     """
#     if request.method != 'POST':
#         return HttpResponse("Nur POST erlaubt", status=HTTPStatus.METHOD_NOT_ALLOWED)
#
#     try:
#         body = request.body.decode('utf-8')
#         callback_data = json.loads(body)
#
#         print(f"📞 Call Callback empfangen: {callback_data}")
#
#         # Hier könntest du zusätzliche Call-Status-Verarbeitung implementieren
#         # Der Unified Bot behandelt bereits die meisten Call Events
#
#         return JsonResponse({"status": "callback_processed"})
#
#     except Exception as e:
#         print(f"❌ Fehler bei Call-Callback: {e}", file=sys.stderr)
#         return JsonResponse({
#             "error": "Callback-Verarbeitung fehlgeschlagen"
#         }, status=HTTPStatus.INTERNAL_SERVER_ERROR)
#
#
# @csrf_exempt
# async def media_stream(request):
#     """
#     Endpoint für Real-time Media Streaming
#     Empfängt Audio-Streams von Teams Calls
#     """
#     if request.method != 'POST':
#         return HttpResponse("Nur POST erlaubt", status=HTTPStatus.METHOD_NOT_ALLOWED)
#
#     try:
#         content_type = request.headers.get('Content-Type', '')
#         conversation_id = request.headers.get('X-Conversation-Id', 'unknown')
#
#         if 'audio' in content_type.lower():
#             # Audio-Stream verarbeiten
#             audio_data = request.body
#
#             print(f"🎵 Audio-Stream empfangen: {len(audio_data)} bytes für Conversation {conversation_id}")
#
#             # Audio direkt an den Bot weiterleiten würde hier passieren
#             # Für jetzt loggen wir nur
#
#             return JsonResponse({
#                 "success": True,
#                 "processed_bytes": len(audio_data),
#                 "conversation_id": conversation_id
#             })
#
#         elif 'application/json' in content_type:
#             # JSON-basierte Media Events
#             data = json.loads(request.body.decode('utf-8'))
#             event_type = data.get('eventType', 'unknown')
#
#             print(f"🎵 Media Event: {event_type}")
#
#             return JsonResponse({
#                 "status": "event_processed",
#                 "eventType": event_type
#             })
#
#         else:
#             return JsonResponse({
#                 "error": "Unsupported media type"
#             }, status=HTTPStatus.BAD_REQUEST)
#
#     except Exception as e:
#         print(f"❌ Fehler bei Media-Stream: {e}", file=sys.stderr)
#         return JsonResponse({
#             "error": "Media-Stream-Verarbeitung fehlgeschlagen"
#         }, status=HTTPStatus.INTERNAL_SERVER_ERROR)

from django.urls import path
from django.http import JsonResponse
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
from tel_bot import VoiceOnlyBot
import json

adapter_settings = BotFrameworkAdapterSettings("", "")  # Kein AppID/AppPassword nötig
adapter = BotFrameworkAdapter(adapter_settings)
bot = VoiceOnlyBot()

# Fehlerbehandlung (optional)
async def on_error(context, error):
    print(f"Bot error: {error}")
adapter.on_turn_error = on_error

async def messages(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            activity = Activity().deserialize(body)
            auth_header = request.headers.get("Authorization", "")

            await adapter.process_activity(activity, auth_header, bot.on_turn)

            # Prüfen ob Audio-Anhang vorlag
            if activity.attachments:
                for att in activity.attachments:
                    if att.content_type.startswith("audio"):
                        return JsonResponse({"status": "success"}, status=200)

            return JsonResponse({"status": "ignored"}, status=200)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


