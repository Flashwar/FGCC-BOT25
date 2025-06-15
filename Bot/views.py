import base64
import io
from allauth.account.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.template.loader import render_to_string
from django_tables2 import RequestConfig
from django_tables2.export import TableExport
from plotly.offline import plot
from django.shortcuts import render
from weasyprint import HTML
import plotly.io as pio
from .services import CustomerService
from .statistics import Statistics
from injector import inject
from Bot.filters import CustomerFilter
from Bot.tables import CustomerTable

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


import sys
import json
from http import HTTPStatus

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

# Bot Framework Core Imports
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
    ConversationState,
    UserState,
    MemoryStorage  # WICHTIG: Ersetze dies in Produktion!
)
from botbuilder.schema import Activity, ActivityTypes

# Importiere deinen Bot (angenommen, er liegt in 'bot_app/bot.py')
from .bot import RegistrationBot

# Bot Framework Adapter Einstellungen
# In Produktion sollten APP_ID und APP_PASSWORD aus Umgebungsvariablen geladen werden.
# Für lokale Tests kannst du sie leer lassen oder Placeholder verwenden.
APP_ID = ""  # Ersetze dies mit deiner Microsoft App ID
APP_PASSWORD = ""  # Ersetze dies mit deinem Microsoft App Password

# Erstelle den Bot Framework Adapter
SETTINGS = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# Speicher für den Zustand.
# ACHTUNG: MemoryStorage ist NICHT für die Produktion geeignet,
# da Daten bei jedem Neustart des Servers verloren gehen!
# Für die Produktion solltest du AzureBlobStorage, CosmosDbStorage etc. verwenden.
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)
USER_STATE = UserState(MEMORY)

# Erstelle eine Instanz deines Bots
# Übergib die Zustands-Manager an den Bot
BOT = RegistrationBot(CONVERSATION_STATE, USER_STATE)


# Fehlermanagement für den Adapter
async def on_error(context: TurnContext, error: Exception):
    # Dies wird aufgerufen, wenn ein Fehler während der Bot-Verarbeitung auftritt.
    print(f"\n [on_error] Unbehandelter Fehler: {error}", file=sys.stderr)
    await context.send_activity("Entschuldigung, es ist ein Fehler aufgetreten und der Bot muss neu starten.")

    # Optional: Den Zustand löschen, um den Bot zurückzusetzen, wenn ein Fehler auftritt
    await CONVERSATION_STATE.delete(context)
    await USER_STATE.delete(context)


# Registriere den Fehlerhandler beim Adapter
ADAPTER.on_turn_error = on_error


@csrf_exempt
async def messages(request):
    """
    Diese Django-View empfängt eingehende HTTP-POST-Anfragen vom Bot Framework Connector.
    """
    if request.method != 'POST':
        return HttpResponse(status=HTTPStatus.METHOD_NOT_ALLOWED)

    # Überprüfe den Content-Type des Requests
    if "application/json" not in request.headers.get("Content-Type", ""):
        return HttpResponse(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    # Lese den Request-Body und deserialisiere ihn in ein Activity-Objekt
    body = request.body.decode('utf-8')
    activity = Activity().deserialize(json.loads(body))

    # Hole den Authorization-Header (wichtig für die Authentifizierung bei Azure Bot Service)
    auth_header = request.headers.get("Authorization", "")

    try:
        # Der Adapter verarbeitet die eingehende Aktivität und ruft die Bot-Logik auf.
        # Die Methode BOT.on_turn wird pro eingehender Aktivität aufgerufen.
        await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        return HttpResponse(status=HTTPStatus.OK)

    except Exception as e:
        # Fange jegliche Fehler ab, die vor oder während der Adapter-Verarbeitung auftreten könnten.
        print(f"Fehler bei der Verarbeitung der Bot-Aktivität: {e}", file=sys.stderr)
        return HttpResponse(status=HTTPStatus.INTERNAL_SERVER_ERROR, text=str(e))
