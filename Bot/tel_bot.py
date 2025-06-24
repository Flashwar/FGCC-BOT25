# bot/audio_registration_bot.py
import aiohttp
import tempfile
import os
from typing import Dict, Any
from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount, Attachment, ActivityTypes
from Bot.azure_service.keyvault import AzureKeyVaultService
from Bot.azure_service.luis_service import AzureCLUService
from Bot.azure_service.speech_service import AzureSpeechService
from .message_bot import RegistrationTextBot, DialogState
from FCCSemesterAufgabe.settings import AZURE_KEYVAULT, isDocker

print("=== AUDIO REGISTRATION BOT WIRD GELADEN ===")


class AudioRegistrationBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        super().__init__()
        print("🎤 Initialisiere Audio Registration Bot...")

        # States
        self.conversation_state = conversation_state
        self.user_state = user_state

        # Unterliegender Text-Bot für die Logik
        self.text_bot = RegistrationTextBot(conversation_state, user_state)

        # Azure Services initialisieren
        try:
            # KeyVault Service sollte von Settings kommen

            self.keyvault = AZURE_KEYVAULT
            if not isDocker:
                self.clu_service= None
                self.speech_service = None
            else:
                self.clu_service = AzureCLUService(self.keyvault)
                self.speech_service = AzureSpeechService(self.keyvault)
            print("✅ Azure Services erfolgreich initialisiert")
        except Exception as e:
            print(f"❌ Fehler bei Azure Services: {e}")
            raise

        # Unterstützte Audio-Formate
        self.supported_audio_types = {
            'audio/ogg',
            'audio/mpeg',
            'audio/wav',
            'audio/webm',
            'audio/mp3',
            'audio/x-wav',
            'audio/wave'
        }

        print("✅ Audio Registration Bot initialisiert")

    async def on_message_activity(self, turn_context: TurnContext):
        """Verarbeitet eingehende Nachrichten - nur Audio wird akzeptiert."""
        print("\n" + "=" * 50)
        print("🎤 AUDIO MESSAGE ACTIVITY")
        print("=" * 50)

        try:
            attachments = turn_context.activity.attachments or []
            print(f"📎 Anzahl Attachments: {len(attachments)}")

            # Zeige alle Attachments für Debugging
            for i, att in enumerate(attachments):
                print(f"  Attachment {i + 1}: {att.content_type} - {att.name}")

            # Filtere Audio-Attachments
            audio_attachments = [
                att for att in attachments
                if att.content_type in self.supported_audio_types
            ]

            print(f"🎵 Audio Attachments gefunden: {len(audio_attachments)}")

            # Nur Audio-Nachrichten verarbeiten
            if not audio_attachments:
                print("❌ Keine Audio-Nachricht - sende Hinweis")
                await self._send_audio_only_message(turn_context)
                return

            # Verarbeite das erste Audio-Attachment
            attachment = audio_attachments[0]
            await self._process_audio_message(turn_context, attachment)

        except Exception as e:
            print(f"❌ Fehler in on_message_activity: {e}")
            import traceback
            traceback.print_exc()

            # Sende Fehler als Audio-Nachricht
            error_text = "Entschuldigung, es gab einen Fehler beim Verarbeiten Ihrer Nachricht."
            await self._send_audio_response(turn_context, error_text)

    async def _process_audio_message(self, turn_context: TurnContext, attachment: Attachment):
        """Verarbeitet eine Audio-Nachricht komplett."""
        print(f"🎤 Verarbeite Audio: {attachment.name}")

        try:
            # 1. Audio herunterladen
            audio_bytes = await self._download_audio(attachment)
            if not audio_bytes:
                await self._send_audio_response(turn_context,
                                                "Entschuldigung, ich konnte die Audio-Datei nicht laden.")
                return

            print(f"📥 Audio heruntergeladen: {len(audio_bytes)} bytes")

            # 2. Speech-to-Text
            stt_result = self.speech_service.speech_to_text_from_bytes(audio_bytes)

            if not stt_result.get('success'):
                error_msg = "Entschuldigung, ich konnte Ihre Sprache nicht verstehen. Bitte sprechen Sie deutlicher."
                await self._send_audio_response(turn_context, error_msg)
                return

            recognized_text = stt_result.get('text', '').strip()
            print(f"🗣️ Erkannter Text: '{recognized_text}'")

            if not recognized_text:
                await self._send_audio_response(turn_context,
                                                "Ich habe nichts verstanden. Bitte sprechen Sie lauter und deutlicher.")
                return

            # 3. CLU Analyse für Intent-Erkennung (optional - für bessere NLU)
            try:
                clu_result = await self.clu_service.analyze_conversation(
                    recognized_text,
                    turn_context.activity.conversation.id
                )
                print(f"🧠 CLU Analyse: {clu_result.get('total_intents_found', 0)} Intents gefunden")

                # Log der erkannten Intents
                if clu_result.get('all_intents'):
                    top_intent = clu_result['all_intents'][0]
                    print(f"   Top Intent: {top_intent['intent']} (Confidence: {top_intent['confidence']:.2f})")

            except Exception as e:
                print(f"⚠️ CLU Analyse fehlgeschlagen: {e}")
                # Fortsetzung ohne CLU

            # 4. Text an den bestehenden Registrierungs-Bot weiterleiten
            # Erstelle eine künstliche Text-Activity
            text_activity = turn_context.activity
            text_activity.text = recognized_text
            text_activity.type = ActivityTypes.message

            # Temporär die Activity überschreiben
            original_activity = turn_context.activity
            turn_context.activity = text_activity

            # 5. Text-Bot Response sammeln (abfangen bevor sie gesendet wird)
            bot_responses = []

            # Wrapper für send_activity um Responses zu sammeln
            original_send = turn_context.send_activity

            async def capture_send(activity):
                if hasattr(activity, 'text'):
                    bot_responses.append(activity.text)
                else:
                    bot_responses.append(str(activity))
                # Original call für State-Management
                return await original_send(activity)

            turn_context.send_activity = capture_send

            # Text-Bot verarbeiten lassen
            await self.text_bot.on_message_activity(turn_context)

            # Original Activity wiederherstellen
            turn_context.activity = original_activity
            turn_context.send_activity = original_send

            # 6. Alle Bot-Responses als Audio senden
            if bot_responses:
                combined_response = " ... ".join(bot_responses)
                print(f"🤖 Bot Antwort: '{combined_response}'")
                await self._send_audio_response(turn_context, combined_response)
            else:
                print("⚠️ Keine Bot-Antwort erhalten")

        except Exception as e:
            print(f"❌ Fehler in _process_audio_message: {e}")
            import traceback
            traceback.print_exc()

            await self._send_audio_response(turn_context,
                                            "Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten.")

    async def _download_audio(self, attachment: Attachment) -> bytes:
        """Lädt Audio-Attachment herunter."""
        try:
            if not attachment.content_url:
                print("❌ Keine Content-URL im Attachment")
                return None

            print(f"📥 Lade Audio herunter: {attachment.content_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.content_url) as response:
                    if response.status == 200:
                        audio_bytes = await response.read()
                        print(f"✅ Audio erfolgreich geladen: {len(audio_bytes)} bytes")
                        return audio_bytes
                    else:
                        print(f"❌ Download fehlgeschlagen: HTTP {response.status}")
                        return None

        except Exception as e:
            print(f"❌ Download Exception: {e}")
            return None

    async def _send_audio_response(self, turn_context: TurnContext, text: str):
        """Sendet eine Antwort als Audio-Nachricht."""
        try:
            print(f"🔊 Generiere Audio für: '{text}'")

            # Text-to-Speech
            audio_bytes = self.speech_service.text_to_speech_bytes(text)

            if not audio_bytes:
                print("❌ TTS fehlgeschlagen - sende Text-Fallback")
                await turn_context.send_activity(MessageFactory.text(
                    f"🔊 [Audio-Nachricht]: {text}"
                ))
                return

            print(f"✅ Audio generiert: {len(audio_bytes)} bytes")

            # Audio als Temporary File speichern und senden
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name

            try:
                # Audio-Attachment erstellen
                with open(temp_file_path, 'rb') as audio_file:
                    audio_data = audio_file.read()

                # Als Inline-Attachment senden (Base64)
                import base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')

                attachment = Attachment(
                    content_type="audio/wav",
                    content_url=f"data:audio/wav;base64,{audio_base64}",
                    name="bot_response.wav"
                )

                # Activity mit Audio-Attachment erstellen
                reply = MessageFactory.attachment(attachment)
                reply.text = f"🔊 Audio-Nachricht: {text[:100]}..." if len(text) > 100 else f"🔊 Audio-Nachricht: {text}"

                await turn_context.send_activity(reply)
                print("✅ Audio-Nachricht gesendet")

            finally:
                # Temporary file löschen
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

        except Exception as e:
            print(f"❌ Fehler beim Senden der Audio-Antwort: {e}")
            import traceback
            traceback.print_exc()

            # Text-Fallback
            await turn_context.send_activity(MessageFactory.text(
                f"🔊 [Audio konnte nicht generiert werden]: {text}"
            ))

    async def _send_audio_only_message(self, turn_context: TurnContext):
        """Sendet Hinweis, dass nur Audio-Nachrichten akzeptiert werden."""
        message = "Hallo! Ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht für die Registrierung."
        await self._send_audio_response(turn_context, message)

    async def on_members_added_activity(self, members_added: [ChannelAccount], turn_context: TurnContext):
        """Begrüßung für neue Mitglieder."""
        print(f"👋 Neue Mitglieder: {len(members_added)}")

        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome_text = (
                    "Willkommen! Ich bin Ihr Sprach-Registrierungs-Bot. "
                    "Ich helfe Ihnen bei der Kundenregistrierung. "
                    "Bitte senden Sie mir eine Sprachnachricht um zu beginnen."
                )
                await self._send_audio_response(turn_context, welcome_text)

                # Dialog-State für den Text-Bot initialisieren
                await self.text_bot.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                break

        # State speichern
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)