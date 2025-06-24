# bot/emulator_views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, ConversationState, UserState, \
    MemoryStorage, TurnContext
from botbuilder.schema import Activity, ActivityTypes
import json
import asyncio
from django.conf import settings
import traceback

print("=== EMULATOR-SICHERE VIEWS LADEN ===")


# Einfacher Audio Bot ohne Azure Services (für erste Tests)
class SimpleTestBot:
    def __init__(self):
        print("🤖 Simple Test Bot initialisiert")
        self.supported_audio_types = {
            'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp3', 'audio/x-wav', 'audio/wave'
        }

    async def on_turn(self, turn_context: TurnContext):
        try:
            print(f"🔄 Simple Bot - Activity: {turn_context.activity.type}")

            if turn_context.activity.type == ActivityTypes.message:
                await self._handle_message(turn_context)
            elif turn_context.activity.type == ActivityTypes.conversation_update:
                await self._handle_conversation_update(turn_context)

        except Exception as e:
            print(f"❌ Simple Bot Error: {e}")
            traceback.print_exc()

    async def _handle_message(self, turn_context: TurnContext):
        """Behandle normale Nachrichten"""
        try:
            attachments = turn_context.activity.attachments or []
            audio_attachments = [att for att in attachments if att.content_type in self.supported_audio_types]

            print(f"📎 Attachments: {len(attachments)}, Audio: {len(audio_attachments)}")

            if audio_attachments:
                # Audio-Nachricht erkannt
                response_text = f"🎵 Audio-Nachricht erhalten! Datei: {audio_attachments[0].name or 'unbekannt'}"
                print(f"📤 Sende Audio-Response: {response_text}")
                await turn_context.send_activity(response_text)
            else:
                # Nur Text-Nachricht
                response_text = "🎤 Bitte senden Sie mir eine Audio-Nachricht für die Registrierung."
                print(f"📤 Sende Text-Response: {response_text}")
                await turn_context.send_activity(response_text)

        except Exception as e:
            print(f"❌ Message Handler Error: {e}")
            # Versuche trotzdem eine Antwort zu senden
            try:
                await turn_context.send_activity("❌ Fehler beim Verarbeiten der Nachricht")
            except Exception as e2:
                print(f"❌ Auch Fehler-Response fehlgeschlagen: {e2}")

    async def _handle_conversation_update(self, turn_context: TurnContext):
        """Behandle Conversation Updates (neue Mitglieder)"""
        try:
            members_added = turn_context.activity.members_added or []
            print(f"👥 Conversation Update: {len(members_added)} Mitglieder hinzugefügt")

            for member in members_added:
                if member.id != turn_context.activity.recipient.id:
                    welcome_text = ("👋 Willkommen! Ich bin Ihr Audio-Registrierungs-Bot. "
                                    "Senden Sie mir eine Sprachnachricht um zu beginnen.")
                    print(f"📤 Sende Willkommen: {welcome_text}")
                    await turn_context.send_activity(welcome_text)
                    break

        except Exception as e:
            print(f"❌ Conversation Update Error: {e}")
            # Bei Conversation Update Fehlern nicht werfen - das ist normal im Emulator


# Bot Setup für Emulator
try:
    print("🔧 Initialisiere Emulator-Bot...")

    # Explizit für Emulator konfigurieren
    bot_settings = BotFrameworkAdapterSettings(
        app_id="",  # Explizit leer für Emulator
        app_password=""  # Explizit leer für Emulator
    )

    print(f"🔧 Bot Settings - App ID: '{bot_settings.app_id}'")
    print(f"🔧 Bot Settings - Password: '{bot_settings.app_password}'")

    adapter = BotFrameworkAdapter(bot_settings)

    # Memory Storage
    memory_storage = MemoryStorage()
    conversation_state = ConversationState(memory_storage)
    user_state = UserState(memory_storage)

    # Einfacher Test Bot
    bot = SimpleTestBot()

    print("✅ Emulator Bot erfolgreich initialisiert")

except Exception as e:
    print(f"❌ Emulator Bot Init Error: {e}")
    traceback.print_exc()
    raise


@csrf_exempt
@require_http_methods(["POST"])
def emulator_messages(request):
    print("\n" + "=" * 50)
    print("🎯 EMULATOR BOT REQUEST")
    print("=" * 50)

    try:
        # Request Details
        print(f"📨 Method: {request.method}")
        print(f"📨 Content-Type: {request.META.get('CONTENT_TYPE', 'nicht gesetzt')}")

        # Body parsen
        try:
            body = json.loads(request.body.decode('utf-8'))
            print(f"✅ JSON erfolgreich geparst")
            print(f"📊 Channel: {body.get('channelId', 'unbekannt')}")
            print(f"📊 Type: {body.get('type', 'unbekannt')}")

            # Attachments loggen
            attachments = body.get('attachments', [])
            if attachments:
                print(f"📎 {len(attachments)} Attachment(s):")
                for i, att in enumerate(attachments):
                    print(f"   {i + 1}. {att.get('contentType', 'unknown')} - {att.get('name', 'unnamed')}")

        except json.JSONDecodeError as e:
            print(f"❌ JSON Parse Error: {e}")
            return JsonResponse({"error": f"JSON Error: {e}"}, status=400)

        # Activity erstellen
        try:
            activity = Activity().deserialize(body)
            print(f"✅ Activity erstellt: {activity.type}")

        except Exception as e:
            print(f"❌ Activity Error: {e}")
            return JsonResponse({"error": f"Activity Error: {e}"}, status=400)

        # Auth Header (für Emulator soll leer sein)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        print(f"🔐 Auth Header: {'[LEER]' if not auth_header else '[GESETZT]'}")

        # Bot Logic mit verbessertem Error Handling
        async def safe_bot_logic(turn_context):
            try:
                print("🤖 Bot Logic startet...")
                await bot.on_turn(turn_context)
                print("✅ Bot Logic erfolgreich")

            except Exception as e:
                print(f"❌ Bot Logic Error: {e}")
                print(f"   Error Type: {type(e).__name__}")

                # Spezielle Behandlung für verschiedene Fehlertypen
                if "Connection refused" in str(e):
                    print("⚠️ Connection Error - normal im Emulator, ignoriere")
                    return  # Ignoriere Connection Errors

                elif "Authorization" in str(e):
                    print("⚠️ Auth Error - sollte nicht passieren im Emulator")
                    return  # Ignoriere Auth Errors

                else:
                    print("❌ Unbekannter Bot Error:")
                    traceback.print_exc()
                    # Versuche eine einfache Fehler-Response
                    try:
                        await turn_context.send_activity("❌ Ein Fehler ist aufgetreten")
                    except:
                        print("❌ Auch Fehler-Response fehlgeschlagen")

        # Event Loop Management
        try:
            print("🔄 Starte Bot Processing...")
            task = adapter.process_activity(activity, auth_header, safe_bot_logic)

            # Robuste Event Loop Behandlung
            try:
                loop = asyncio.get_running_loop()
                print("📍 Verwende bestehenden Event Loop")

                # Timeout für Sicherheit
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, task)
                    future.result(timeout=10)  # 10 Sekunden Timeout

            except (RuntimeError, TimeoutError) as e:
                print(f"📍 Event Loop Problem: {e}")
                print("📍 Erstelle neuen Event Loop")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(task)
                except asyncio.TimeoutError:
                    print("⏰ Task Timeout")
                finally:
                    loop.close()

            print("🎉 Request erfolgreich verarbeitet")
            return JsonResponse({
                "status": "success",
                "bot": "emulator_safe",
                "activity_type": activity.type
            })

        except Exception as e:
            print(f"❌ Processing Error: {e}")
            error_msg = str(e)

            # Behandle spezifische Errors
            if "Authorization" in error_msg or "auth" in error_msg.lower():
                print("⚠️ Auth Error - versuche ohne Auth")
                return JsonResponse({
                    "status": "auth_error_ignored",
                    "message": "Auth Error im Emulator ignoriert"
                })

            elif "Connection refused" in error_msg:
                print("⚠️ Connection Error - normal im Emulator")
                return JsonResponse({
                    "status": "connection_error_ignored",
                    "message": "Connection Error im Emulator ignoriert"
                })

            else:
                print(f"❌ Unbehandelter Error: {error_msg}")
                traceback.print_exc()
                return JsonResponse({
                    "error": f"Processing Error: {error_msg}",
                    "type": type(e).__name__
                }, status=500)

    except Exception as e:
        print(f"💥 Unerwarteter Request Error: {e}")
        traceback.print_exc()
        return JsonResponse({
            "error": f"Request Error: {e}",
            "traceback": traceback.format_exc()
        }, status=500)


# Test Endpoint
@csrf_exempt
def emulator_test(request):
    return JsonResponse({
        "message": "Emulator Bot endpoint erreichbar!",
        "bot_type": "SimpleTestBot (Emulator-sicher)",
        "features": ["Audio-Erkennung", "Text-Fallback", "Robust Error Handling"]
    })