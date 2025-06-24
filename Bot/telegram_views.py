# bot/telegram_views.py - Für echten Telegram Bot
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, ConversationState, UserState, \
    MemoryStorage
from botbuilder.schema import Activity
import json
import asyncio
from django.conf import settings
import traceback

print("=== TELEGRAM BOT VIEWS LADEN ===")


# Telegram-spezifische Bot-Klasse
class TelegramAudioBot:
    def __init__(self):
        print("📱 Telegram Audio Bot initialisiert")
        self.supported_audio_types = {
            'audio/ogg',  # Telegram Voice Messages
            'audio/mpeg',  # MP3
            'audio/wav',  # WAV
            'audio/mp4',  # Telegram Audio
            'audio/webm',  # Telegram Web Audio
        }

    async def on_turn(self, turn_context):
        try:
            activity_type = turn_context.activity.type
            print(f"📱 Telegram Activity: {activity_type}")

            if activity_type == "message":
                await self._handle_telegram_message(turn_context)
            else:
                print(f"📱 Telegram - Activity Type ignoriert: {activity_type}")

        except Exception as e:
            print(f"❌ Telegram Bot Error: {e}")
            traceback.print_exc()

    async def _handle_telegram_message(self, turn_context):
        try:
            message_text = turn_context.activity.text or ""
            attachments = turn_context.activity.attachments or []

            print(f"📱 Telegram Message - Text: '{message_text}'")
            print(f"📱 Telegram Message - Attachments: {len(attachments)}")

            # Prüfe auf Audio-Attachments
            audio_attachments = []
            for att in attachments:
                print(f"   Attachment: {att.content_type} - {att.name}")
                if att.content_type in self.supported_audio_types:
                    audio_attachments.append(att)

            if audio_attachments:
                # Audio-Nachricht verarbeiten
                attachment = audio_attachments[0]
                await self._process_telegram_audio(turn_context, attachment)

            else:
                # Nur Text oder keine Audio
                response = ("🎤 Willkommen beim Audio-Registrierungsbot! "
                            "Bitte senden Sie mir eine Sprachnachricht für die Registrierung.")
                await turn_context.send_activity(response)

        except Exception as e:
            print(f"❌ Telegram Message Error: {e}")
            await turn_context.send_activity("❌ Fehler beim Verarbeiten der Nachricht.")

    async def _process_telegram_audio(self, turn_context, attachment):
        try:
            print(f"🎵 Verarbeite Telegram Audio: {attachment.name}")
            print(f"🎵 Content Type: {attachment.content_type}")
            print(f"🎵 Content URL: {attachment.content_url}")

            # Hier würdest du die Azure Speech Services einbauen
            # Für jetzt: einfache Bestätigung

            file_name = attachment.name or "Sprachnachricht"
            response = f"✅ Audio erhalten: {file_name}. Verarbeitung wird implementiert..."

            await turn_context.send_activity(response)

        except Exception as e:
            print(f"❌ Telegram Audio Error: {e}")
            await turn_context.send_activity("❌ Fehler beim Verarbeiten der Audio-Datei.")


# Bot Setup für Telegram (mit echten Credentials)
try:
    print("📱 Initialisiere Telegram Bot...")

    # WICHTIG: Für Telegram MÜSSEN echte Credentials gesetzt werden
    app_id = settings.APP_ID
    app_password = settings.APP_PASSWORD

    print(f"📱 App ID: {app_id}")
    print(f"📱 App Password gesetzt: {bool(app_password)}")

    if not app_id or not app_password:
        print("⚠️ WARNUNG: Keine Azure Credentials - Telegram wird nicht funktionieren!")
        print("⚠️ Setze MICROSOFT_APP_ID und MICROSOFT_APP_PASSWORD in settings.py")

    # Bot Settings mit echten Credentials
    bot_settings = BotFrameworkAdapterSettings(
        app_id=app_id,
        app_password=app_password
    )

    adapter = BotFrameworkAdapter(bot_settings)

    # Memory Storage
    memory_storage = MemoryStorage()
    conversation_state = ConversationState(memory_storage)
    user_state = UserState(memory_storage)

    # Telegram Bot
    telegram_bot = TelegramAudioBot()

    print("✅ Telegram Bot Setup abgeschlossen")

except Exception as e:
    print(f"❌ Telegram Bot Init Error: {e}")
    traceback.print_exc()
    raise


@csrf_exempt
@require_http_methods(["POST"])
def telegram_messages(request):
    print("\n" + "=" * 50)
    print("📱 TELEGRAM BOT REQUEST")
    print("=" * 50)

    try:
        # Request Details
        print(f"📨 Method: {request.method}")
        print(f"📨 Content-Type: {request.META.get('CONTENT_TYPE', 'nicht gesetzt')}")
        print(f"📨 User-Agent: {request.META.get('HTTP_USER_AGENT', 'nicht gesetzt')}")

        # Authorization Header prüfen
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        print(f"🔐 Auth Header vorhanden: {bool(auth_header)}")
        if auth_header:
            print(f"🔐 Auth Header Prefix: {auth_header[:50]}...")

        # Body parsen
        try:
            body = json.loads(request.body.decode('utf-8'))
            print(f"✅ JSON erfolgreich geparst")
            print(f"📊 Channel: {body.get('channelId', 'unbekannt')}")
            print(f"📊 Type: {body.get('type', 'unbekannt')}")
            print(f"📊 Service URL: {body.get('serviceUrl', 'keine')}")

            # From User Info
            from_user = body.get('from', {})
            print(f"👤 From User: {from_user.get('name', 'unbekannt')} (ID: {from_user.get('id', 'keine')})")

            # Text
            text = body.get('text', '')
            if text:
                print(f"💬 Text: '{text}'")

            # Attachments
            attachments = body.get('attachments', [])
            if attachments:
                print(f"📎 {len(attachments)} Attachment(s):")
                for i, att in enumerate(attachments):
                    print(f"   {i + 1}. {att.get('contentType', 'unknown')} - {att.get('name', 'unnamed')}")
                    print(f"      URL: {att.get('contentUrl', 'no URL')[:100]}...")

        except json.JSONDecodeError as e:
            print(f"❌ JSON Parse Error: {e}")
            return JsonResponse({"error": f"JSON Error: {e}"}, status=400)

        # Activity erstellen
        try:
            activity = Activity().deserialize(body)
            print(f"✅ Activity erstellt: {activity.type}")

        except Exception as e:
            print(f"❌ Activity Error: {e}")
            traceback.print_exc()
            return JsonResponse({"error": f"Activity Error: {e}"}, status=400)

        # Bot Logic
        async def telegram_bot_logic(turn_context):
            try:
                print("📱 Telegram Bot Logic startet...")
                await telegram_bot.on_turn(turn_context)
                print("✅ Telegram Bot Logic erfolgreich")

            except Exception as e:
                print(f"❌ Telegram Bot Logic Error: {e}")
                traceback.print_exc()

                # Versuche Fehler-Response zu senden
                try:
                    await turn_context.send_activity("❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.")
                except Exception as e2:
                    print(f"❌ Auch Fehler-Response fehlgeschlagen: {e2}")

        # Event Loop
        try:
            print("🔄 Starte Telegram Bot Processing...")
            task = adapter.process_activity(activity, auth_header, telegram_bot_logic)

            # Event Loop Management
            try:
                loop = asyncio.get_running_loop()
                print("📍 Verwende bestehenden Event Loop")

                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, task)
                    future.result(timeout=30)  # 30 Sekunden Timeout für Telegram

            except (RuntimeError, TimeoutError) as e:
                print(f"📍 Event Loop Problem: {e}")
                print("📍 Erstelle neuen Event Loop")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(task)
                finally:
                    loop.close()

            print("🎉 Telegram Request erfolgreich verarbeitet")
            return JsonResponse({
                "status": "success",
                "bot": "telegram_audio_bot",
                "activity_type": activity.type
            })

        except Exception as e:
            print(f"❌ Telegram Processing Error: {e}")
            error_msg = str(e)

            # Spezifische Telegram Errors
            if "Unauthorized" in error_msg:
                print("❌ Azure Authentication Fehler!")
                print("   Prüfe MICROSOFT_APP_ID und MICROSOFT_APP_PASSWORD in settings.py")
                print("   Prüfe Azure Bot Service Konfiguration")
                return JsonResponse({
                    "error": "Azure Authentication failed",
                    "message": "Prüfe Bot Service Credentials",
                    "app_id": getattr(settings, 'MICROSOFT_APP_ID', 'NICHT_GESETZT')
                }, status=401)

            elif "Invalid AppId" in error_msg:
                print("❌ Ungültige Azure App ID!")
                return JsonResponse({
                    "error": "Invalid Azure App ID",
                    "message": "App ID stimmt nicht mit Azure Bot Service überein"
                }, status=401)

            else:
                print(f"❌ Anderer Telegram Error: {error_msg}")
                traceback.print_exc()
                return JsonResponse({
                    "error": f"Telegram Processing Error: {error_msg}",
                    "type": type(e).__name__
                }, status=500)

    except Exception as e:
        print(f"💥 Unerwarteter Telegram Request Error: {e}")
        traceback.print_exc()
        return JsonResponse({
            "error": f"Telegram Request Error: {e}",
            "traceback": traceback.format_exc()
        }, status=500)


# Test Endpoint für Telegram
def telegram_test(request):
    app_id = settings.APP_ID
    app_password = settings.APP_PASSWORD
    return JsonResponse({
        "message": "Telegram Bot endpoint erreichbar!",
        "bot_type": "TelegramAudioBot",
        "credentials_check": {
            "app_id_set": bool(app_id),
            "app_id": app_id if app_id else "NICHT_GESETZT",
            "app_password_set": bool(app_password),
            "ready_for_telegram": bool(app_id and app_password)
        },
        "required_setup": [
            "1. Azure Bot Service erstellen",
            "2. App ID und Password in settings.py setzen",
            "3. Telegram Channel in Azure konfigurieren",
            "4. Webhook URL in Telegram setzen"
        ]
    })