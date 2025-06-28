import aiohttp
import base64
import re
from datetime import datetime
from typing import Optional
from injector import inject

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount, Attachment

from .audio_converter import FFmpegAudioConverter
from .dialogstate import DialogState
from .validators import DataValidator
from .services import CustomerService
from .text_messages import BotMessages, FieldConfig
from .azure_service.speech_service import AzureSpeechService
from FCCSemesterAufgabe.settings import isDocker


print("=== AUDIO REGISTRATION BOT WIRD GELADEN ===")


class RegistrationAudioBot(ActivityHandler):
    """
    Audio-basierter Registrierungsbot mit identischer Struktur wie RegistrationTextBot.
    Akzeptiert nur Audio-Input und gibt nur Audio-Output aus.
    Bei Text-Input wird Fehler ausgegeben, aber State beibehalten.
    """

    @inject
    def __init__(self, conversation_state: ConversationState, user_state: UserState, customer_service: CustomerService):

        # Core Services
        self.customer_service = customer_service
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.audio_converter = FFmpegAudioConverter()

        # State Accessors
        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")

        # Azure Services initialisieren
        if isDocker:
            print("⚠️ KeyVault Service nicht verfügbar")
            self.speech_service = None
        else:
            self.speech_service = AzureSpeechService()
            test_audio = self.speech_service.text_to_speech_bytes("Test")
            if test_audio and len(test_audio) > 0:
                print(f"✅ Speech Service funktioniert! TTS Test: {len(test_audio)} bytes")
            else:
                raise Exception("Speech Service TTS Test fehlgeschlagen")

        # Audio Format Unterstützung
        self.supported_audio_types = {
            'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp3',
            'audio/x-wav', 'audio/wave', 'audio/opus', 'audio/aac', 'audio/m4a'
        }

        self.azure_compatible_formats = {
            'audio/wav', 'audio/x-wav', 'audio/wave'
        }

        # Dialog Handlers
        self.dialog_handlers = {
            DialogState.GREETING: self._handle_greeting,
            DialogState.ASK_CONSENT: self._handle_consent_input,
            DialogState.ASK_GENDER: self._handle_gender_input,
            DialogState.ASK_TITLE: self._handle_title_input,
            DialogState.ASK_FIRST_NAME: self._handle_first_name_input,
            DialogState.ASK_LAST_NAME: self._handle_last_name_input,
            DialogState.ASK_BIRTHDATE: self._handle_birthdate_input,
            DialogState.ASK_EMAIL: self._handle_email_input,
            DialogState.ASK_PHONE: self._handle_phone_input,
            DialogState.ASK_STREET: self._handle_street_input,
            DialogState.ASK_HOUSE_NUMBER: self._handle_house_number_input,
            DialogState.ASK_HOUSE_ADDITION: self._handle_house_addition_input,
            DialogState.ASK_POSTAL: self._handle_postal_input,
            DialogState.ASK_CITY: self._handle_city_input,
            DialogState.ASK_COUNTRY: self._handle_country_input,
            DialogState.FINAL_CONFIRMATION: self._handle_final_confirmation,
            "correction_selection": self._handle_correction_selection,
        }

        # Dialog Flow (identisch zum Text-Bot)
        self.dialog_flow = [
            ("confirm_gender", self._ask_for_title, self._ask_for_gender),
            ("confirm_title", self._ask_for_first_name, self._ask_for_title),
            ("confirm_first_name", self._ask_for_last_name, self._ask_for_first_name),
            ("confirm_last_name", self._ask_for_birthdate, self._ask_for_last_name),
            ("confirm_birthdate", self._ask_for_email, self._ask_for_birthdate),
            ("confirm_email", self._ask_for_phone, self._ask_for_email),
            ("confirm_phone", self._ask_for_street, self._ask_for_phone),
            ("confirm_street", self._ask_for_house_number, self._ask_for_street),
            ("confirm_house_number", self._ask_for_house_addition, self._ask_for_house_number),
            ("confirm_house_addition", self._ask_for_postal, self._ask_for_house_addition),
            ("confirm_postal", self._ask_for_city, self._ask_for_postal),
            ("confirm_city", self._ask_for_country, self._ask_for_city),
            ("confirm_country", self._show_final_summary, self._ask_for_country),
        ]

        print("✅ Audio Registration Bot initialisiert")

    # === MAIN MESSAGE HANDLING (identische Struktur wie Text-Bot) ===

    async def on_message_activity(self, turn_context: TurnContext):
        """
        Hauptmethode für Nachrichten-Verarbeitung.
        Identische Struktur wie Text-Bot, aber mit Audio-Validierung.
        """
        print("\n" + "=" * 50)
        print("🎤 AUDIO MESSAGE RECEIVED")
        print("=" * 50)

        try:
            # 1. Prüfe auf /start Kommando (vor Audio-Validierung!)
            text_input = turn_context.activity.text
            if text_input and text_input.strip().lower() == '/start':
                await self._handle_start_command(turn_context)
                return

            # 2. Input-Typ validieren und extrahieren
            user_input = await self._extract_and_validate_input(turn_context)
            if user_input is None:  # Fehler beim Input oder ungültiger Typ
                return

            # 3. User Profile und Dialog State abrufen (identisch zum Text-Bot)
            user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
            dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

            print(f"🎯 Current State: {dialog_state}")
            print(f"🗣️ User Input: '{user_input}'")

            # 4. Auto-start für neue User (identisch zum Text-Bot)
            if not user_profile and dialog_state == DialogState.GREETING:
                user_profile['first_interaction'] = True
                await self.user_profile_accessor.set(turn_context, user_profile)
                await self._handle_greeting(turn_context, user_profile)
                await self._save_state(turn_context)
                return

            # 5. Dialog-Routing (identische Logik wie Text-Bot)
            if dialog_state == DialogState.COMPLETED:
                await self._handle_completed_state(turn_context, user_profile, user_input)
            elif dialog_state == "restart_confirmation":
                await self._handle_restart_confirmation(turn_context, user_profile, user_input)
            elif dialog_state == "correction_selection":
                await self._handle_correction_selection(turn_context, user_profile, user_input)
            elif dialog_state.startswith(DialogState.CONFIRM_PREFIX):
                await self._handle_confirmation(turn_context, user_profile, user_input, dialog_state)
            elif dialog_state in self.dialog_handlers:
                await self.dialog_handlers[dialog_state](turn_context, user_profile, user_input)
            else:
                await self._handle_unknown_state(turn_context, user_profile, user_input)

            # 6. State speichern (identisch zum Text-Bot)
            await self._save_state(turn_context)

        except Exception as e:
            print(f"❌ Fehler in on_message_activity: {e}")
            await self._send_audio_response(turn_context,
                                            "Entschuldigung, es gab einen Fehler. Bitte versuchen Sie es erneut.")

    async def on_members_added_activity(self, members_added: [ChannelAccount], turn_context: TurnContext):
        """Identisch zum Text-Bot"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                await self._handle_greeting(turn_context,
                                            await self.user_profile_accessor.get(turn_context, lambda: {}))
                break

        await self._save_state(turn_context)

    async def _handle_start_command(self, turn_context: TurnContext):
        """
        Behandelt /start Kommando.
        - Wenn in Registrierung: Bestätigung erfragen
        - Wenn bereits fertig/nicht gestartet: Direkt neu starten
        """
        print("🔄 /start Kommando erkannt")

        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

        # Prüfe ob User bereits in aktiver Registrierung ist
        is_in_registration = self._is_in_active_registration(dialog_state, user_profile)

        if is_in_registration:
            # User ist mitten in der Registrierung - Bestätigung erfragen
            print(f"🤔 User ist in aktiver Registrierung (State: {dialog_state})")
            await self._ask_restart_confirmation(turn_context)
        else:
            # User ist nicht in aktiver Registrierung - direkt neu starten
            print(f"✅ User nicht in aktiver Registrierung (State: {dialog_state}) - direkter Neustart")
            await self._execute_restart(turn_context)

        await self._save_state(turn_context)

    def _is_in_active_registration(self, dialog_state: str, user_profile: dict) -> bool:
        """
        Prüft ob User sich in einer aktiven Registrierung befindet.
        """
        # States die als "aktive Registrierung" gelten
        active_registration_states = [
            DialogState.ASK_CONSENT,
            DialogState.ASK_GENDER,
            DialogState.ASK_TITLE,
            DialogState.ASK_FIRST_NAME,
            DialogState.ASK_LAST_NAME,
            DialogState.ASK_BIRTHDATE,
            DialogState.ASK_EMAIL,
            DialogState.ASK_PHONE,
            DialogState.ASK_STREET,
            DialogState.ASK_HOUSE_NUMBER,
            DialogState.ASK_HOUSE_ADDITION,
            DialogState.ASK_POSTAL,
            DialogState.ASK_CITY,
            DialogState.ASK_COUNTRY,
            DialogState.FINAL_CONFIRMATION,
            "correction_selection",
        ]

        # Auch alle Bestätigungs-States
        if dialog_state.startswith(DialogState.CONFIRM_PREFIX):
            return True

        # Prüfe normale Registration-States
        if dialog_state in active_registration_states:
            return True

        # Prüfe ob User bereits Daten eingegeben hat (auch bei GREETING)
        if dialog_state == DialogState.GREETING and user_profile:
            # Wenn User schon mal Daten eingegeben hat, ist es eine Fortsetzung
            has_registration_data = any(key in user_profile for key in [
                'consent_given', 'gender', 'first_name', 'last_name',
                'email', 'telephone', 'street_name'
            ])
            return has_registration_data

        return False

    async def _ask_restart_confirmation(self, turn_context: TurnContext):
        """
        Fragt User ob wirklich neu gestartet werden soll.
        """
        # Speichere aktuellen State um später zurückkehren zu können
        current_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        user_profile['previous_state'] = current_state
        await self.user_profile_accessor.set(turn_context, user_profile)

        confirmation_text = (
            "Sie sind gerade mitten in der Registrierung. "
            "Möchten Sie wirklich von vorne beginnen? "
            "Alle bisherigen Eingaben gehen dabei verloren. "
            "Sagen Sie 'ja' zum Neustarten oder 'nein' zum Fortfahren."
        )

        await self._send_audio_response(turn_context, confirmation_text)
        await self.dialog_state_accessor.set(turn_context, "restart_confirmation")

    async def _handle_restart_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """
        Behandelt die Antwort auf die Neustart-Bestätigung.
        """
        user_input_lower = user_input.lower().strip()

        if any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES):
            # User möchte wirklich neu starten
            print("✅ User bestätigt Neustart")
            await self._send_audio_response(turn_context, "Verstanden. Ich starte die Registrierung neu.")
            await self._execute_restart(turn_context)

        elif any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES):
            # User möchte nicht neu starten - zurück zum vorherigen State
            print("✅ User möchte nicht neu starten - kehre zum Dialog zurück")
            await self._send_audio_response(turn_context, "In Ordnung. Dann setzen wir fort.")

            # Kehre zum vorherigen Dialog-State zurück (der vor restart_confirmation war)
            previous_state = user_profile.get('previous_state', DialogState.GREETING)
            await self.dialog_state_accessor.set(turn_context, previous_state)

        else:
            # Unklare Antwort
            await self._send_audio_response(turn_context,
                                            "Bitte antworten Sie mit 'ja' um neu zu starten oder 'nein' um fortzufahren.")

    async def _execute_restart(self, turn_context: TurnContext):
        """
        Führt den eigentlichen Neustart durch.
        """
        print("🔄 Führe Neustart durch...")

        # Alles zurücksetzen
        await self.user_profile_accessor.set(turn_context, {})
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

        # Neue Registrierung starten
        await self._handle_greeting(turn_context, {})

    # === INPUT VALIDATION UND AUDIO PROCESSING ===

    async def _extract_and_validate_input(self, turn_context: TurnContext) -> Optional[str]:
        """
        Validiert Input-Typ und extrahiert Text aus Audio.
        Bei Text-Input: Fehler ausgeben, aber State beibehalten.
        Bei Audio-Input: STT durchführen.
        """
        attachments = turn_context.activity.attachments or []
        audio_attachments = [att for att in attachments if att.content_type in self.supported_audio_types]
        text_input = turn_context.activity.text

        # Fall 1: Text-Input erkannt (State wird beibehalten!)
        if text_input and text_input.strip() and not audio_attachments:
            print(f"❌ Text-Input erkannt: '{text_input}' - State wird beibehalten")
            await self._send_audio_response(turn_context,
                                            "Entschuldigung, ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht anstatt Text.")
            return None

        # Fall 2: Kein Audio-Input
        if not audio_attachments:
            print("❌ Kein Audio-Input erkannt")
            await self._send_audio_response(turn_context,
                                            "Hallo! Ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht.")
            return None

        # Fall 3: Audio-Input verarbeiten
        return await self._process_audio_input(turn_context, audio_attachments[0])

    async def _process_audio_input(self, turn_context: TurnContext, attachment: Attachment) -> Optional[str]:
        """
        Verarbeitet Audio-Attachment mit FFmpeg-Konvertierung und STT
        """
        try:
            # Audio herunterladen
            audio_bytes = await self._download_audio(attachment)
            if not audio_bytes:
                await self._send_audio_response(turn_context, "Audio konnte nicht geladen werden.")
                return None

            # Audio validieren und konvertieren
            processed_audio = await self._validate_and_convert_audio(audio_bytes, attachment.content_type)
            if not processed_audio:
                await self._send_audio_response(turn_context,
                                                "Das Audio-Format konnte nicht verarbeitet werden. Bitte versuchen Sie eine andere Aufnahme.")
                return None

            # Speech-to-Text
            stt_result = self.speech_service.speech_to_text_from_bytes(processed_audio)
            print(f"🎤 STT Result: {stt_result}")

            if stt_result.get('success'):
                recognized_text = stt_result.get('text', '').strip()
                print(f"🗣️ STT Erkannt: '{recognized_text}'")

                # Text anzeigen
                await self._send_recognized_text_display(turn_context, recognized_text)
                return recognized_text
            else:
                error_msg = stt_result.get('error', 'Unbekannter STT-Fehler')
                await self._handle_stt_error(turn_context, error_msg)
                return None

        except Exception as e:
            print(f"❌ Fehler bei Audio-Verarbeitung: {e}")
            await self._send_audio_response(turn_context, "Fehler beim Verarbeiten der Sprache.")
            return None

    async def _download_audio(self, attachment: Attachment) -> Optional[bytes]:
        """Audio-Download mit Validierung"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.content_url) as response:
                    if response.status == 200:
                        audio_bytes = await response.read()
                        if len(audio_bytes) == 0:
                            print("❌ Audio-Datei ist leer")
                            return None
                        if len(audio_bytes) < 100:
                            print(f"❌ Audio-Datei zu klein: {len(audio_bytes)} bytes")
                            return None
                        return audio_bytes
                    else:
                        print(f"❌ HTTP Fehler: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ Audio Download Fehler: {e}")
            return None

    async def _validate_and_convert_audio(self, audio_bytes: bytes, content_type: str) -> Optional[bytes]:
        """Audio-Validierung und FFmpeg-Konvertierung"""
        try:
            # Prüfe ob bereits Azure-kompatibel
            if content_type in self.azure_compatible_formats:
                validated_audio = self._validate_wav_header(audio_bytes)
                if validated_audio:
                    return validated_audio

            # FFmpeg-Konvertierung
            if self.audio_converter.ffmpeg_available:
                return await self.audio_converter.convert_to_azure_wav(audio_bytes)
            else:
                print(f"❌ FFmpeg nicht verfügbar - {content_type} wird nicht unterstützt")
                return None

        except Exception as e:
            print(f"❌ Audio-Validierung fehlgeschlagen: {e}")
            return None

    def _validate_wav_header(self, audio_bytes: bytes) -> Optional[bytes]:
        """WAV-Header Validierung"""
        try:
            if len(audio_bytes) < 44:
                return None
            if audio_bytes[:4] != b'RIFF' or audio_bytes[8:12] != b'WAVE':
                return None
            return audio_bytes
        except:
            return None

    # === AUDIO OUTPUT ===

    async def _send_audio_response(self, turn_context: TurnContext, text: str):
        """Sendet NUR Audio-Antworten mit Längen-Optimierung"""
        try:
            print(f"🔊 Generiere Audio für: '{text[:100]}{'...' if len(text) > 100 else ''}'")

            # Text für Sprache optimieren
            speech_text = self._convert_markdown_to_speech(text)

            # Text in kleinere Chunks aufteilen wenn zu lang
            chunks = self._split_text_for_tts(speech_text)

            for i, chunk in enumerate(chunks):
                try:
                    # TTS für jeden Chunk
                    audio_bytes = self.speech_service.text_to_speech_bytes(chunk)

                    if audio_bytes and len(audio_bytes) > 0:
                        # Prüfe Audio-Größe (Telegram-Limit: ~50MB, aber besser kleiner halten)
                        if len(audio_bytes) > 10 * 1024 * 1024:  # 10MB Limit
                            print(f"⚠️ Audio-Chunk {i + 1} zu groß ({len(audio_bytes)} bytes) - überspringe")
                            continue

                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                        # Prüfe Base64-Größe (Telegram entity limit)
                        if len(audio_base64) > 200000:  # ~200KB Base64 Limit
                            print(f"⚠️ Base64-Chunk {i + 1} zu groß ({len(audio_base64)} chars) - sende Fallback")
                            await self._send_text_fallback(turn_context, chunk)
                            continue

                        attachment = Attachment(
                            content_type="audio/wav",
                            content_url=f"data:audio/wav;base64,{audio_base64}",
                            name=f"bot_response_{i + 1}.wav"
                        )
                        reply = MessageFactory.attachment(attachment)
                        await turn_context.send_activity(reply)
                        print(f"✅ Audio-Chunk {i + 1}/{len(chunks)} gesendet")

                        # Kurze Pause zwischen Chunks
                        if len(chunks) > 1 and i < len(chunks) - 1:
                            import asyncio
                            await asyncio.sleep(0.5)

                    else:
                        print(f"❌ TTS für Chunk {i + 1} fehlgeschlagen")
                        await self._send_text_fallback(turn_context, chunk)

                except Exception as chunk_error:
                    print(f"❌ Fehler bei Chunk {i + 1}: {chunk_error}")
                    await self._send_text_fallback(turn_context, chunk)

        except Exception as e:
            print(f"❌ Allgemeiner TTS Fehler: {e}")
            await self._send_text_fallback(turn_context, text)

    def _split_text_for_tts(self, text: str, max_length: int = 500) -> list[str]:
        """
        Teilt Text in TTS-freundliche Chunks auf.
        Versucht bei Satzenden zu trennen.
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining_text = text

        while remaining_text:
            if len(remaining_text) <= max_length:
                chunks.append(remaining_text.strip())
                break

            # Suche nach einem guten Trennpunkt (Satzende)
            chunk = remaining_text[:max_length]

            # Versuche bei Punkt zu trennen
            last_period = chunk.rfind('. ')
            if last_period > max_length * 0.6:  # Mindestens 60% der gewünschten Länge
                split_pos = last_period + 1
            else:
                # Versuche bei Komma zu trennen
                last_comma = chunk.rfind(', ')
                if last_comma > max_length * 0.7:  # Mindestens 70% der gewünschten Länge
                    split_pos = last_comma + 1
                else:
                    # Versuche bei Leerzeichen zu trennen
                    last_space = chunk.rfind(' ')
                    if last_space > max_length * 0.8:  # Mindestens 80% der gewünschten Länge
                        split_pos = last_space
                    else:
                        # Harte Trennung
                        split_pos = max_length

            chunk = remaining_text[:split_pos].strip()
            if chunk:
                chunks.append(chunk)

            remaining_text = remaining_text[split_pos:].strip()

        print(f"📝 Text in {len(chunks)} Chunks aufgeteilt")
        return chunks

    async def _send_text_fallback(self, turn_context: TurnContext, text: str):
        """
        Fallback: Sendet Text wenn Audio nicht funktioniert.
        Nur als letzte Option verwenden.
        """
        try:
            fallback_message = f"🔊 [Audio nicht verfügbar] {text[:500]}{'...' if len(text) > 500 else ''}"
            await turn_context.send_activity(MessageFactory.text(fallback_message))
            print("📝 Text-Fallback gesendet")
        except Exception as e:
            print(f"❌ Auch Text-Fallback fehlgeschlagen: {e}")

    async def _send_recognized_text_display(self, turn_context: TurnContext, recognized_text: str):
        """
        Zeigt erkannten Text als Audio-Bestätigung.
        """
        try:
            # Statt Text-Display: Audio-Bestätigung was verstanden wurde
            confirmation_text = f"Ich habe verstanden: {recognized_text}"

            # Kurze Audio-Bestätigung senden
            speech_text = self._convert_markdown_to_speech(confirmation_text)
            audio_bytes = self.speech_service.text_to_speech_bytes(speech_text)

            if audio_bytes and len(audio_bytes) > 0:
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                attachment = Attachment(
                    content_type="audio/wav",
                    content_url=f"data:audio/wav;base64,{audio_base64}",
                    name="recognition_confirmation.wav"
                )
                reply = MessageFactory.attachment(attachment)
                await turn_context.send_activity(reply)
                print("✅ Audio-Bestätigung der Spracherkennung gesendet")

        except Exception as e:
            print(f"❌ Fehler bei Audio-Bestätigung der Spracherkennung: {e}")

    def _convert_markdown_to_speech(self, text: str) -> str:
        """Konvertiert Markdown zu sprachfreundlichem Text"""
        speech_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** -> bold
        speech_text = re.sub(r'\*([^*]+)\*', r'\1', speech_text)  # *italic* -> italic
        speech_text = re.sub(r'•\s*', '', speech_text)  # Bullet points entfernen
        speech_text = re.sub(r'\n+', ' ', speech_text)  # Zeilenumbrüche zu Leerzeichen
        speech_text = re.sub(r'\s+', ' ', speech_text)  # Mehrfache Leerzeichen entfernen
        return speech_text.strip()


    # === DIALOG HANDLERS (Identisch zum Text-Bot, nur mit Audio-Output) ===

    async def _handle_greeting(self, turn_context: TurnContext, user_profile, *args):
        """Begrüßung (identisch zum Text-Bot)"""
        greeting_text = self._convert_markdown_to_speech(BotMessages.WELCOME_MESSAGE)
        await self._send_audio_response(turn_context, greeting_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CONSENT)

    async def _handle_consent_input(self, turn_context: TurnContext, user_profile, user_input):
        """Consent-Behandlung (identisch zum Text-Bot)"""
        user_input_lower = user_input.lower().strip()

        if any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES):
            consent_text = self._convert_markdown_to_speech(BotMessages.CONSENT_GRANTED)
            await self._send_audio_response(turn_context, consent_text)
            user_profile['consent_given'] = True
            user_profile['consent_timestamp'] = datetime.now().isoformat()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._ask_for_gender(turn_context)

        elif any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES):
            denied_text = self._convert_markdown_to_speech(BotMessages.CONSENT_DENIED)
            await self._send_audio_response(turn_context, denied_text)
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
            await self.user_profile_accessor.set(turn_context, {
                'consent_given': False,
                'consent_timestamp': datetime.now().isoformat(),
                'registration_cancelled': True
            })
        else:
            unclear_text = self._convert_markdown_to_speech(BotMessages.CONSENT_UNCLEAR)
            await self._send_audio_response(turn_context, unclear_text)

    async def _ask_for_gender(self, turn_context: TurnContext):
        """Geschlecht-Abfrage"""
        gender_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['gender'])
        await self._send_audio_response(turn_context, gender_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_GENDER)

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile, user_input):
        """Geschlecht-Verarbeitung"""
        user_input_lower = user_input.lower()

        if user_input_lower in FieldConfig.GENDER_OPTIONS:
            gender_value, gender_display = FieldConfig.GENDER_OPTIONS[user_input_lower]
            user_profile['gender'] = gender_value
            user_profile['gender_display'] = gender_display
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'gender', 'Geschlecht', gender_display):
                return

            await self._confirm_field(turn_context, "Geschlecht", gender_display, DialogState.CONFIRM_PREFIX + "gender")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['gender'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_title(self, turn_context: TurnContext):
        """Titel-Abfrage"""
        title_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['title'])
        await self._send_audio_response(turn_context, title_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_TITLE)

    async def _handle_title_input(self, turn_context: TurnContext, user_profile, user_input):
        """Titel-Verarbeitung"""
        user_input_strip_lower = user_input.strip().lower()

        if user_input_strip_lower in FieldConfig.NO_TITLE_KEYWORDS:
            user_profile['title'] = ''
            user_profile['title_display'] = "Kein Titel"
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'title', 'Titel', "Kein Titel"):
                return

            await self._confirm_field(turn_context, "Titel", "Kein Titel", DialogState.CONFIRM_PREFIX + "title")
        elif user_input in FieldConfig.VALID_TITLES:
            user_profile['title'] = user_input
            user_profile['title_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'title', 'Titel', user_input):
                return

            await self._confirm_field(turn_context, "Titel", user_input, DialogState.CONFIRM_PREFIX + "title")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['title'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_first_name(self, turn_context: TurnContext):
        """Vorname-Abfrage"""
        name_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['first_name'])
        await self._send_audio_response(turn_context, name_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_FIRST_NAME)

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Vorname-Verarbeitung"""
        if DataValidator.validate_name_part(user_input):
            user_profile['first_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'first_name', 'Vorname', user_input):
                return

            await self._confirm_field(turn_context, "Vorname", user_input, DialogState.CONFIRM_PREFIX + "first_name")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['first_name'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_last_name(self, turn_context: TurnContext):
        """Nachname-Abfrage"""
        name_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['last_name'])
        await self._send_audio_response(turn_context, name_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_LAST_NAME)

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Nachname-Verarbeitung"""
        if DataValidator.validate_name_part(user_input):
            user_profile['last_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'last_name', 'Nachname', user_input):
                return

            await self._confirm_field(turn_context, "Nachname", user_input, DialogState.CONFIRM_PREFIX + "last_name")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['last_name'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        """Geburtsdatum-Abfrage"""
        birthdate_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['birthdate'])
        await self._send_audio_response(turn_context, birthdate_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile, user_input):
        """Geburtsdatum-Verarbeitung mit Speech-Extraktion"""
        # Versuche normale Validation und Speech-spezifische Extraktion
        birthdate = DataValidator.validate_birthdate(user_input)
        if not birthdate:
            birthdate = self._extract_birthdate_from_speech(user_input)

        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = birthdate.strftime('%d.%m.%Y')
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'birth_date', 'Geburtsdatum',
                                                            birthdate.strftime('%d.%m.%Y')):
                return

            await self._confirm_field(turn_context, "Geburtsdatum", birthdate.strftime('%d.%m.%Y'),
                                      DialogState.CONFIRM_PREFIX + "birthdate")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['birthdate'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_email(self, turn_context: TurnContext):
        """E-Mail-Abfrage"""
        email_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['email'])
        await self._send_audio_response(turn_context, email_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile, user_input):
        """E-Mail-Verarbeitung mit Speech-Extraktion"""
        email = self._extract_email_from_speech(user_input)
        if not email:
            email = user_input.strip()

        if DataValidator.validate_email(email):
            if not user_profile.get('correction_mode'):
                if await self.customer_service.email_exists_in_db(email.strip().lower()):
                    error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['email_exists'])
                    await self._send_audio_response(turn_context, error_text)
                    return

            user_profile['email'] = email.strip().lower()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'email', 'E-Mail', email):
                return

            await self._confirm_field(turn_context, "E-Mail", email, DialogState.CONFIRM_PREFIX + "email")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['email'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_phone(self, turn_context: TurnContext):
        """Telefon-Abfrage"""
        phone_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['phone'])
        await self._send_audio_response(turn_context, phone_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_PHONE)

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile, user_input):
        """Telefon-Verarbeitung"""
        phone = self._extract_phone_from_speech(user_input)
        phone_number_obj = DataValidator.validate_phone(phone or user_input)

        if phone_number_obj:
            user_profile['telephone'] = phone_number_obj.as_e164
            user_profile['telephone_display'] = phone or user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'telephone', 'Telefonnummer', phone or user_input):
                return

            await self._confirm_field(turn_context, "Telefonnummer", phone or user_input,
                                      DialogState.CONFIRM_PREFIX + "phone")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['phone'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_street(self, turn_context: TurnContext):
        """Straße-Abfrage"""
        street_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['street'])
        await self._send_audio_response(turn_context, street_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_STREET)

    async def _handle_street_input(self, turn_context: TurnContext, user_profile, user_input):
        """Straße-Verarbeitung"""
        if len(user_input.strip()) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', user_input.strip()):
            user_profile['street_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'street_name', 'Straße', user_input):
                return

            await self._confirm_field(turn_context, "Straße", user_input, DialogState.CONFIRM_PREFIX + "street")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['street'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_house_number(self, turn_context: TurnContext):
        """Hausnummer-Abfrage"""
        house_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['house_number'])
        await self._send_audio_response(turn_context, house_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_NUMBER)

    async def _handle_house_number_input(self, turn_context: TurnContext, user_profile, user_input):
        """Hausnummer-Verarbeitung"""
        try:
            house_number = int(user_input.strip())
            if house_number > 0:
                user_profile['house_number'] = house_number
                await self.user_profile_accessor.set(turn_context, user_profile)

                if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                                'house_number', 'Hausnummer', str(house_number)):
                    return

                await self._confirm_field(turn_context, "Hausnummer", str(house_number),
                                          DialogState.CONFIRM_PREFIX + "house_number")
            else:
                raise ValueError()
        except ValueError:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['house_number'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_house_addition(self, turn_context: TurnContext):
        """Hausnummernzusatz-Abfrage"""
        addition_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['house_addition'])
        await self._send_audio_response(turn_context, addition_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_ADDITION)

    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile, user_input):
        """Hausnummernzusatz-Verarbeitung"""
        if user_input.lower() in FieldConfig.NO_ADDITION_KEYWORDS:
            user_profile['house_number_addition'] = ""
            user_profile['house_addition_display'] = "Kein Zusatz"
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'house_number_addition', 'Hausnummernzusatz',
                                                            "Kein Zusatz"):
                return

            await self._confirm_field(turn_context, "Hausnummernzusatz", "Kein Zusatz",
                                      DialogState.CONFIRM_PREFIX + "house_addition")
        else:
            user_profile['house_number_addition'] = user_input.strip()
            user_profile['house_addition_display'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'house_number_addition', 'Hausnummernzusatz', user_input):
                return

            await self._confirm_field(turn_context, "Hausnummernzusatz", user_input,
                                      DialogState.CONFIRM_PREFIX + "house_addition")

    async def _ask_for_postal(self, turn_context: TurnContext):
        """Postleitzahl-Abfrage"""
        postal_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['postal'])
        await self._send_audio_response(turn_context, postal_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_POSTAL)

    async def _handle_postal_input(self, turn_context: TurnContext, user_profile, user_input):
        """Postleitzahl-Verarbeitung"""
        if DataValidator.validate_postal_code(user_input):
            user_profile['postal_code'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'postal_code', 'Postleitzahl', user_input):
                return

            await self._confirm_field(turn_context, "Postleitzahl", user_input, DialogState.CONFIRM_PREFIX + "postal")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['postal'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_city(self, turn_context: TurnContext):
        """Stadt-Abfrage"""
        city_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['city'])
        await self._send_audio_response(turn_context, city_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CITY)

    async def _handle_city_input(self, turn_context: TurnContext, user_profile, user_input):
        """Stadt-Verarbeitung"""
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', user_input.strip()):
            user_profile['city'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'city', 'Ort', user_input):
                return

            await self._confirm_field(turn_context, "Ort", user_input, DialogState.CONFIRM_PREFIX + "city")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['city'])
            await self._send_audio_response(turn_context, error_text)

    async def _ask_for_country(self, turn_context: TurnContext):
        """Land-Abfrage"""
        country_text = self._convert_markdown_to_speech(BotMessages.FIELD_PROMPTS['country'])
        await self._send_audio_response(turn_context, country_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_COUNTRY)

    async def _handle_country_input(self, turn_context: TurnContext, user_profile, user_input):
        """Land-Verarbeitung"""
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', user_input.strip()):
            user_profile['country_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'country_name', 'Land', user_input):
                return

            await self._confirm_field(turn_context, "Land", user_input, DialogState.CONFIRM_PREFIX + "country")
        else:
            error_text = self._convert_markdown_to_speech(BotMessages.VALIDATION_ERRORS['country'])
            await self._send_audio_response(turn_context, error_text)

    # === CONFIRMATION UND FINAL HANDLING ===

    async def _confirm_field(self, turn_context: TurnContext, field_name: str, value: str, confirmation_state: str):
        """Feld-Bestätigung (Audio-Version)"""
        confirmation_message = BotMessages.confirmation_prompt(field_name, value)
        confirmation_text = self._convert_markdown_to_speech(confirmation_message)
        await self._send_audio_response(turn_context, confirmation_text)
        await self.dialog_state_accessor.set(turn_context, confirmation_state)

    async def _handle_confirmation(self, turn_context: TurnContext, user_profile, user_input, dialog_state):
        """Bestätigung verarbeiten (identisch zum Text-Bot)"""
        user_input_lower = user_input.lower()
        confirmed = user_input_lower in FieldConfig.CONFIRMATION_YES
        rejected = user_input_lower in FieldConfig.CONFIRMATION_NO

        if confirmed:
            found_next_step = False
            for conf_state, next_ask_func, _ in self.dialog_flow:
                if dialog_state == conf_state:
                    await next_ask_func(turn_context)
                    found_next_step = True
                    break
            if not found_next_step and dialog_state == DialogState.CONFIRM_PREFIX + "country":
                await self._show_final_summary(turn_context)
        elif rejected:
            found_correction_step = False
            for conf_state, _, correction_ask_func in self.dialog_flow:
                if dialog_state == conf_state:
                    rejected_text = self._convert_markdown_to_speech(BotMessages.CONFIRMATION_REJECTED)
                    await self._send_audio_response(turn_context, rejected_text)
                    await correction_ask_func(turn_context)
                    found_correction_step = True
                    break
            if not found_correction_step:
                await self._send_audio_response(turn_context,
                    "Entschuldigung, ich kann diesen Schritt nicht korrigieren.")
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        else:
            unclear_text = self._convert_markdown_to_speech(BotMessages.CONFIRMATION_UNCLEAR)
            await self._send_audio_response(turn_context, unclear_text)

    async def _show_final_summary(self, turn_context: TurnContext):
        """Finale Zusammenfassung (Audio-Version)"""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        summary_message = BotMessages.final_summary(user_profile)
        summary_text = self._convert_markdown_to_speech(summary_message)
        await self._send_audio_response(turn_context, summary_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.FINAL_CONFIRMATION)

    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """Finale Bestätigung (identisch zum Text-Bot)"""
        user_input_lower = user_input.lower().strip()

        if any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES):
            save_text = self._convert_markdown_to_speech(BotMessages.SAVE_IN_PROGRESS)
            await self._send_audio_response(turn_context, save_text)

            success = await self._save_customer_data(user_profile)

            if success:
                success_text = self._convert_markdown_to_speech(BotMessages.REGISTRATION_SUCCESS)
                await self._send_audio_response(turn_context, success_text)
                await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
                await self.user_profile_accessor.set(turn_context, {
                    'registration_completed': True,
                    'completion_timestamp': datetime.now().isoformat()
                })
            else:
                error_text = self._convert_markdown_to_speech(BotMessages.SAVE_ERROR)
                await self._send_audio_response(turn_context, error_text)
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)

        elif any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES):
            await self._start_correction_process(turn_context, user_profile)

        elif any(response in user_input_lower for response in FieldConfig.RESTART_KEYWORDS):
            await self._handle_restart_request(turn_context)

        else:
            unclear_text = self._convert_markdown_to_speech(BotMessages.FINAL_CONFIRMATION_UNCLEAR)
            await self._send_audio_response(turn_context, unclear_text)

    # === CORRECTION HANDLING ===

    async def _start_correction_process(self, turn_context: TurnContext, user_profile):
        """Korrektur-Prozess starten (Audio-Version)"""
        correction_text = self._convert_markdown_to_speech(BotMessages.CORRECTION_OPTIONS)
        await self._send_audio_response(turn_context, correction_text)
        await self.dialog_state_accessor.set(turn_context, "correction_selection")

    async def _handle_correction_selection(self, turn_context: TurnContext, user_profile, user_input):
        """Korrektur-Auswahl verarbeiten (identisch zum Text-Bot)"""
        user_input_lower = user_input.lower().strip()

        # Handle special commands
        if user_input_lower in ["zurück", "back", "summary", "zusammenfassung"]:
            await self._show_final_summary(turn_context)
            return
        elif user_input_lower in ["neustart", "restart", "von vorne"]:
            await self._handle_restart_request(turn_context)
            return

        # Process correction selection
        target_field = None
        for key, field in FieldConfig.CORRECTION_MAPPING.items():
            if key in user_input_lower:
                target_field = field
                break

        if target_field:
            dialog_state_mapping = {
                'gender': DialogState.ASK_GENDER,
                'title': DialogState.ASK_TITLE,
                'first_name': DialogState.ASK_FIRST_NAME,
                'last_name': DialogState.ASK_LAST_NAME,
                'birthdate': DialogState.ASK_BIRTHDATE,
                'email': DialogState.ASK_EMAIL,
                'phone': DialogState.ASK_PHONE,
                'street': DialogState.ASK_STREET,
                'house_number': DialogState.ASK_HOUSE_NUMBER,
                'house_addition': DialogState.ASK_HOUSE_ADDITION,
                'postal': DialogState.ASK_POSTAL,
                'city': DialogState.ASK_CITY,
                'country': DialogState.ASK_COUNTRY,
            }

            target_state = dialog_state_mapping.get(target_field)
            field_display = FieldConfig.FIELD_DISPLAY_NAMES.get(target_field, "das gewählte Feld")

            correction_message = BotMessages.correction_start(field_display)
            correction_text = self._convert_markdown_to_speech(correction_message)
            await self._send_audio_response(turn_context, correction_text)

            await self.dialog_state_accessor.set(turn_context, target_state)
            user_profile['correction_mode'] = True
            user_profile['correction_return_to'] = 'final_summary'
            await self.user_profile_accessor.set(turn_context, user_profile)

        else:
            not_understood_text = self._convert_markdown_to_speech(BotMessages.CORRECTION_NOT_UNDERSTOOD)
            await self._send_audio_response(turn_context, not_understood_text)

    async def _check_correction_mode_and_handle(self, turn_context: TurnContext, user_profile,
                                                field_name, field_display, new_value):
        """Korrektur-Modus behandeln (identisch zum Text-Bot)"""
        if user_profile.get('correction_mode'):
            correction_message = BotMessages.correction_success(field_display, new_value)
            correction_text = self._convert_markdown_to_speech(correction_message)
            await self._send_audio_response(turn_context, correction_text)

            user_profile['correction_mode'] = False
            await self.user_profile_accessor.set(turn_context, user_profile)

            await self._show_final_summary(turn_context)
            return True

        return False

    # === STATE HANDLING ===

    async def _handle_completed_state(self, turn_context: TurnContext, user_profile, user_input):
        """Completed State (Audio-Version)"""
        user_input_lower = user_input.lower()

        if any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            if user_profile.get('registration_cancelled'):
                restart_text = self._convert_markdown_to_speech(BotMessages.RESTART_NEW_REGISTRATION)
                await self._send_audio_response(turn_context, restart_text)

                await self.user_profile_accessor.set(turn_context, {})
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                await self._handle_greeting(turn_context, {})

            elif user_profile.get('consent_given') and not user_profile.get('registration_cancelled'):
                already_text = self._convert_markdown_to_speech(BotMessages.ALREADY_REGISTERED)
                await self._send_audio_response(turn_context, already_text)
        else:
            if user_profile.get('registration_cancelled'):
                help_text = self._convert_markdown_to_speech(BotMessages.REGISTRATION_CANCELLED_HELP)
                await self._send_audio_response(turn_context, help_text)
            else:
                help_text = self._convert_markdown_to_speech(BotMessages.ALREADY_COMPLETED_HELP)
                await self._send_audio_response(turn_context, help_text)

    async def _handle_unknown_state(self, turn_context: TurnContext, user_profile, user_input):
        """Unknown State (Audio-Version)"""
        user_input_lower = user_input.lower()

        if any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            restart_text = self._convert_markdown_to_speech(BotMessages.UNKNOWN_STATE_RESTART)
            await self._send_audio_response(turn_context, restart_text)

            await self.user_profile_accessor.set(turn_context, {})
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
            await self._handle_greeting(turn_context, {})
        else:
            confusion_text = self._convert_markdown_to_speech(BotMessages.UNKNOWN_STATE_CONFUSION)
            await self._send_audio_response(turn_context, confusion_text)
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)

    async def _handle_restart_request(self, turn_context: TurnContext):
        """Restart Request (Audio-Version)"""
        restart_text = self._convert_markdown_to_speech(BotMessages.RESTART_MESSAGE)
        await self._send_audio_response(turn_context, restart_text)

        await self.user_profile_accessor.set(turn_context, {})
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
        await self._handle_greeting(turn_context, {})

    # === SPEECH-SPEZIFISCHE EXTRAKTION ===

    def _extract_birthdate_from_speech(self, text: str) -> Optional[datetime]:
        """Extrahiert Geburtsdatum aus gesprochenem Text"""
        try:
            date_patterns = [
                r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
                r'(\d{1,2}) (\d{1,2}) (\d{4})',
                r'(\d{1,2})\s*punkt\s*(\d{1,2})\s*punkt\s*(\d{4})',
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    day, month, year = map(int, match.groups())
                    if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2010:
                        return datetime(year, month, day)
            return None
        except:
            return None

    def _extract_email_from_speech(self, text: str) -> Optional[str]:
        """Extrahiert E-Mail aus gesprochenem Text"""
        speech_corrections = {
            ' at ': '@', ' ät ': '@', ' punkt ': '.', ' dot ': '.',
            ' minus ': '-', ' unterstrich ': '_',
        }

        corrected_text = text.lower()
        for speech_form, correct_form in speech_corrections.items():
            corrected_text = corrected_text.replace(speech_form, correct_form)

        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, corrected_text)
        return match.group() if match else None

    def _extract_phone_from_speech(self, text: str) -> Optional[str]:
        """Extrahiert Telefonnummer aus gesprochenem Text"""
        digits = re.sub(r'[^\d+]', '', text)

        speech_corrections = {
            'null': '0', 'eins': '1', 'zwei': '2', 'drei': '3', 'vier': '4',
            'fünf': '5', 'sechs': '6', 'sieben': '7', 'acht': '8', 'neun': '9',
        }

        corrected_text = text.lower()
        for word, digit in speech_corrections.items():
            corrected_text = corrected_text.replace(word, digit)

        corrected_digits = re.sub(r'[^\d+]', '', corrected_text)
        return corrected_digits if len(corrected_digits) >= 10 else digits if len(digits) >= 10 else None

    # === ERROR HANDLING ===

    async def _handle_stt_error(self, turn_context: TurnContext, error_msg: str):
        """STT-Fehlerbehandlung"""
        error_responses = {
            "INVALID_HEADER": "Das Audio-Format konnte trotz Konvertierung nicht verarbeitet werden.",
            "0xa": "Die Audio-Datei scheint beschädigt zu sein.",
            "NoMatch": "Ich konnte keine Sprache erkennen. Sprechen Sie bitte deutlicher.",
            "Canceled": "Die Spracherkennung wurde unterbrochen.",
            "timeout": "Die Audio-Datei ist zu lang. Bitte senden Sie eine kürzere Nachricht."
        }

        response = "Ich konnte Sie nicht verstehen. Bitte versuchen Sie es erneut."
        for error_key, error_response in error_responses.items():
            if error_key.lower() in error_msg.lower():
                response = error_response
                break

        await self._send_audio_response(turn_context, response)

    # === UTILITY METHODS ===

    async def _save_customer_data(self, user_profile: dict) -> bool:
        """Speichert Kundendaten (identisch zum Text-Bot)"""
        try:
            return await self.customer_service.store_data_db(user_profile.copy())
        except Exception as e:
            print(f"❌ Fehler beim Speichern: {e}")
            return False

    async def _save_state(self, turn_context: TurnContext):
        """Speichert Bot-States (identisch zum Text-Bot)"""
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)