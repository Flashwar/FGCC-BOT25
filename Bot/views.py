import base64
import io
import json
import asyncio
import traceback

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
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, ConversationState, UserState, \
    MemoryStorage
from botbuilder.schema import Activity
from .BotFactory import create_bot_instances
from FCCSemesterAufgabe.settings import APP_ID, APP_PASSWORD, BOT_FRAMEWORK_BOT_ID, BOT_FRAMEWORK_SECRET

# BotFramework Adapter Setup
try:
    adapter_settings = BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD)
    adapter = BotFrameworkAdapter(adapter_settings)
except Exception as e:
    print(f"Adapter Setup Error: {e}")
    raise

# Bot Instance creation
try:
    bot_instances = create_bot_instances()
    tele_bot = bot_instances['tele_bot']
    web_bot = bot_instances['web_bot']
    conversation_state = bot_instances['conversation_state']
    user_state = bot_instances['user_state']
except Exception as e:
    print(f"❌ Bot-Instanzen Error: {e}")
    raise

# Mapping of channel names to bot instances
CHANNEL_BOT_MAPPING = {
    "telegram": {
        "bot": tele_bot,
        "name": "Telegram Audio Bot",
        "supports": ["audio"]
    },
    "webchat": {
        "bot": web_bot,
        "name": "Webchat Text Bot",
        "supports": ["text"]
    },
    "emulator": {
        "bot": web_bot,
        "name": "Emulator Test Bot",
        "supports": ["text"]
    },
    "directline": {
        "bot": web_bot,
        "name": "DirectLine Web Bot",
        "supports": ["text"]
    }
}

# checks if the user is a admin
def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)


# login view
class SuperuserLoginView(LoginView):
    def form_valid(self, form):
        user = form.user
        # checks if the credentials are from an admin
        if not user.is_superuser:
            messages.error(self.request, "Nur für Superuser.")
            return self.form_invalid(form)
        # if true -> login
        return super().form_valid(form)


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


# Generate Charts
def generate_pdf_from_charts(chart_data, total_customers):
    charts = []
    for title, fig in chart_data:
        image_bytes = pio.to_image(fig, format="png", width=800, height=500)
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        charts.append({
            "title": title,
            "image_base64": base64_image
        })
    # Render HTML
    html_string = render_to_string('pdf_stats_template.html', {
        'charts': charts,
        'total_customers': total_customers,
    })

    # convert to pdf and return the file
    pdf = HTML(string=html_string).write_pdf()
    return HttpResponse(
        pdf,
        content_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename="kunden_statistiken_gesamt.pdf"'}
    )


@inject
def customer_stats_pdf(request, chart_type: str, statistics: Statistics, customer_service: CustomerService):
    # get number of total customers
    total_customers = customer_service.get_total_count()

    # prepare chart data with labels and figures
    chart_data = [
        ("Titelverteilung", statistics.get_title_chart()),
        ("Geschlechterverteilung", statistics.get_gender_chart()),
        ("Kunden pro Land", statistics.get_country_chart()),
        ("Altersverteilung", statistics.get_age_chart()),
    ]

    # select chart based on requested type and generate PDF
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
            # generate a combined PDF with all charts
            return generate_pdf_from_charts(chart_data, total_customers)
        case _:
            # return error response for invalid chart type
            return HttpResponse("Ungültiger Chart-Typ", status=400)


def webchat(request):
    # render webchat site
    return render(request, 'webchat.html', context={
        'bot_id': BOT_FRAMEWORK_BOT_ID,
        'bot_secret': BOT_FRAMEWORK_SECRET
    })

@csrf_exempt
@require_http_methods(["POST"])
def messages(request):
    print("\n" + "=" * 60)
    print("📨 MULTI-BOT MESSAGE ROUTING")
    print("=" * 60)

    try:
        # Request Info
        print(f"📨 Method: {request.method}")
        print(f"📨 Content-Type: {request.META.get('CONTENT_TYPE', 'nicht gesetzt')}")
        print(f"📨 User-Agent: {request.META.get('HTTP_USER_AGENT', 'nicht gesetzt')}")

        # Authorization Header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        print(f"🔐 Auth Header: {'vorhanden' if auth_header else 'fehlt'}")

        # Body parsen
        try:
            body = json.loads(request.body.decode('utf-8'))
            print("✅ JSON erfolgreich geladen")
        except json.JSONDecodeError as e:
            print(f"❌ JSON Parse Error: {e}")
            return JsonResponse({"error": "Ungültiges JSON"}, status=400)

        # Activity Details
        channel_id = body.get("channelId", "unknown").lower()
        activity_type = body.get("type", "unknown")
        from_user = body.get("from", {})
        attachments = body.get("attachments", [])
        text = body.get("text", "")

        print(f"🔍 Channel: {channel_id}")
        print(f"📊 Activity: {activity_type}")
        print(f"👤 From: {from_user.get('name', 'Unknown')} (ID: {from_user.get('id', 'none')})")

        if text:
            print(f"💬 Text: '{text[:100]}{'...' if len(text) > 100 else ''}'")
        if attachments:
            print(f"📎 Attachments: {len(attachments)}")
            for i, att in enumerate(attachments):
                print(f"   {i + 1}. {att.get('contentType', 'unknown')} - {att.get('name', 'unnamed')}")

        # Activity erstellen
        try:
            activity = Activity().deserialize(body)
            print("✅ Activity erfolgreich erstellt")
        except Exception as e:
            print(f"❌ Activity Creation Error: {e}")
            traceback.print_exc()
            return JsonResponse({"error": "Ungültige Activity"}, status=400)

        # Bot-Auswahl basierend auf Channel
        if channel_id in CHANNEL_BOT_MAPPING:
            bot_config = CHANNEL_BOT_MAPPING[channel_id]
            selected_bot = bot_config["bot"]
            bot_name = bot_config["name"]

            print(f"🤖 Ausgewählter Bot: {bot_name}")
            print(f"🎯 Unterstützt: {', '.join(bot_config['supports'])}")
        else:
            print(f"❌ Unbekannter Channel: {channel_id}")
            print(f"🔧 Verfügbare Channels: {', '.join(CHANNEL_BOT_MAPPING.keys())}")

            # Fallback zum ersten verfügbaren Bot
            fallback_config = list(CHANNEL_BOT_MAPPING.values())[0]
            selected_bot = fallback_config["bot"]
            bot_name = f"{fallback_config['name']} (Fallback)"

            print(f"🔄 Fallback zu: {bot_name}")

        # Bot Logic
        async def bot_logic(turn_context):
            try:
                print(f"🚀 {bot_name} startet...")
                await selected_bot.on_turn(turn_context)
                print(f"✅ {bot_name} erfolgreich ausgeführt")

            except Exception as e:
                print(f"❌ Bot Error in {bot_name}: {e}")
                print(f"❌ Error Type: {type(e).__name__}")
                traceback.print_exc()

                # Versuche Fehler-Response zu senden
                try:
                    error_message = f"❌ Ein Fehler ist aufgetreten in {channel_id}. Bitte versuchen Sie es erneut."
                    await turn_context.send_activity(error_message)
                except Exception as e2:
                    print(f"❌ Auch Error-Response fehlgeschlagen: {e2}")

        # Adapter Verarbeitung
        print("🔄 Starte Bot Processing...")
        task = adapter.process_activity(activity, auth_header, bot_logic)

        # Event Loop Management (deine bewährte Lösung)
        try:
            loop = asyncio.get_running_loop()
            print("📍 Verwende bestehenden Event Loop")

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, task)
                future.result(timeout=30)  # 30s Timeout

        except (RuntimeError, TimeoutError) as e:
            print(f"📍 Event Loop Problem: {e}")
            print("📍 Erstelle neuen Event Loop")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(task)
            finally:
                loop.close()

        print("🎉 Multi-Bot Request erfolgreich verarbeitet")
        return JsonResponse({
            "status": "success",
            "channel": channel_id,
            "bot": bot_name,
            "activity_type": activity.type,
            "supports": bot_config.get("supports", ["unknown"])
        })

    except Exception as e:
        print(f"💥 Unerwarteter Multi-Bot Error: {e}")
        print(f"💥 Error Type: {type(e).__name__}")
        traceback.print_exc()

        return JsonResponse({
            "error": f"Multi-Bot Error: {e}",
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }, status=500)
