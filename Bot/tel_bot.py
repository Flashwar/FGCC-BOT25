import aiohttp
import base64
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from injector import inject

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount, Attachment

from .audio_converter import FFmpegAudioConverter
from .dialogstate import DialogState
from .validators import DataValidator
from .services import CustomerService
from .text_speech_bot import SpeechBotMessages
from .text_messages import FieldConfig
from .azure_service.speech_service import AzureSpeechService
from .azure_service.luis_service import AzureCLUService
from .azure_service.storage_service import BlobService
from FCCSemesterAufgabe.settings import isDocker


class RegistrationAudioBot(ActivityHandler):
    """
    Clean audio-only registration bot with comprehensive CLU integration.
    Mirrors the structure of RegistrationTextBot but exclusively handles audio input/output.
    """

    @inject
    def __init__(self, conversation_state: ConversationState, user_state: UserState, customer_service: CustomerService):
        # Core services
        self.customer_service = customer_service
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.audio_converter = FFmpegAudioConverter()

        # State accessors
        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")

        # Initialize Azure services
        if isDocker:
            print("⚠️ Running in Docker - Azure services disabled")
            self.speech_service = None
            self.clu_service = None
            self.audio_blob_uploader = None
        else:
            # Initialize Speech Service
            try:
                self.audio_blob_uploader = BlobService()
                self.speech_service = AzureSpeechService()
                test_audio = self.speech_service.text_to_speech_bytes("Test")
                if test_audio and len(test_audio) > 0:
                    print(f"✅ Speech Service initialized: {len(test_audio)} bytes")
                else:
                    raise Exception("Speech Service TTS test failed")
            except Exception as e:
                print(f"❌ Speech Service initialization failed: {e}")
                self.speech_service = None

            # Initialize CLU Service
            try:
                self.clu_service = AzureCLUService()
                print("✅ CLU Service initialized")
            except Exception as e:
                print(f"❌ CLU Service initialization failed: {e}")
                self.clu_service = None

        # Audio format support
        self.supported_audio_types = {
            'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp3',
            'audio/x-wav', 'audio/wave', 'audio/opus', 'audio/aac', 'audio/m4a'
        }

        # Dialog handlers (identical structure to text bot)
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

        # Dialog flow (identical to text bot)
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

        print("✅ Audio Registration Bot initialized")

    # === MAIN MESSAGE HANDLING ===

    async def on_message_activity(self, turn_context: TurnContext):
        """Main message handler - processes audio input and /start command"""
        print("\n" + "=" * 50)
        print("🎤 AUDIO MESSAGE RECEIVED")
        print("=" * 50)

        try:
            # Check for /start command FIRST (before audio validation)
            text_input = turn_context.activity.text
            if text_input and text_input.strip().lower() == '/start':
                await self._handle_start_command(turn_context)
                return

            # Extract and validate input (audio only for normal flow)
            user_input = await self._extract_and_validate_input(turn_context)
            if user_input is None:
                return

            # Get current state
            user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
            dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

            print(f"🎯 Current State: {dialog_state}")
            print(f"🗣️ User Input: '{user_input}'")

            # Auto-start for new users
            if not user_profile and dialog_state == DialogState.GREETING:
                user_profile['first_interaction'] = True
                await self.user_profile_accessor.set(turn_context, user_profile)
                await self._handle_greeting(turn_context, user_profile)
                await self._save_state(turn_context)
                return

            # Route to appropriate handler
            if dialog_state == DialogState.COMPLETED:
                await self._handle_completed_state(turn_context, user_profile, user_input)
            elif dialog_state == "correction_selection":
                await self._handle_correction_selection(turn_context, user_profile, user_input)
            elif dialog_state.startswith(DialogState.CONFIRM_PREFIX):
                await self._handle_confirmation(turn_context, user_profile, user_input, dialog_state)
            elif dialog_state in self.dialog_handlers:
                await self.dialog_handlers[dialog_state](turn_context, user_profile, user_input)
            else:
                await self._handle_unknown_state(turn_context, user_profile, user_input)

            # Save state
            await self._save_state(turn_context)

        except Exception as e:
            print(f"❌ Error in on_message_activity: {e}")
            await self._send_audio_response(turn_context,
                                            "Entschuldigung, es gab einen Fehler. Bitte versuchen Sie es erneut.")

    async def on_members_added_activity(self, members_added: [ChannelAccount], turn_context: TurnContext):
        """Handle new members joining - send welcome with /start instruction"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

                # Send welcome message with /start instruction
                welcome_text = (
                    "Willkommen! Ich bin Ihr Audio-Registrierungsassistent. "
                    "Schreiben Sie /start um die Registrierung zu beginnen, "
                    "oder senden Sie eine Sprachnachricht."
                )
                await self._send_audio_and_text_response(turn_context, welcome_text)
                break
        await self._save_state(turn_context)

    async def _handle_start_command(self, turn_context: TurnContext):
        """Handle /start command to begin or restart registration"""
        print(" /start command received")

        # Reset everything and start fresh
        await self.user_profile_accessor.set(turn_context, {})
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

        # Start new registration
        await self._handle_greeting(turn_context, {})
        await self._save_state(turn_context)

    # === INPUT VALIDATION AND PROCESSING ===

    async def _extract_and_validate_input(self, turn_context: TurnContext) -> Optional[str]:
        """Extract and validate audio input, reject other text input (except /start)"""
        attachments = turn_context.activity.attachments or []
        audio_attachments = [att for att in attachments if att.content_type in self.supported_audio_types]
        text_input = turn_context.activity.text

        # Allow /start command (already handled in main method)
        if text_input and text_input.strip().lower() == '/start':
            return None  # This should not reach here as it's handled earlier

        # Reject other text input
        if text_input and text_input.strip() and not audio_attachments:
            print(f"❌ Text input rejected: '{text_input}' (only /start allowed)")
            await self._send_audio_and_text_response(turn_context,
                                                     "Entschuldigung, ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht oder verwenden Sie /start zum Neubeginn.")
            return None

        # Require audio input
        if not audio_attachments:
            print("❌ No audio input detected")
            await self._send_audio_and_text_response(turn_context,
                                                     "Hallo! Ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht oder schreiben Sie /start.")
            return None

        # Process audio input
        return await self._process_audio_input(turn_context, audio_attachments[0])

    async def _process_audio_input(self, turn_context: TurnContext, attachment: Attachment) -> Optional[str]:
        """Process audio attachment with STT and CLU"""
        try:
            # Download audio
            audio_bytes = await self._download_audio(attachment)
            if not audio_bytes:
                await self._send_audio_response(turn_context, "Audio konnte nicht geladen werden.")
                return None

            # Convert to compatible format
            processed_audio = await self._convert_audio(audio_bytes, attachment.content_type)
            if not processed_audio:
                await self._send_audio_response(turn_context,
                                                "Das Audio-Format konnte nicht verarbeitet werden.")
                return None

            # Speech-to-Text
            if not self.speech_service:
                await self._send_audio_response(turn_context, "Spracherkennung ist nicht verfügbar.")
                return None

            stt_result = self.speech_service.speech_to_text_from_bytes(processed_audio)
            print(f"🎤 STT Result: {stt_result}")

            if stt_result.get('success'):
                recognized_text = stt_result.get('text', '').strip()
                print(f"🗣️ Recognized: '{recognized_text}'")
                return recognized_text
            else:
                error_msg = stt_result.get('error', 'Unknown STT error')
                await self._handle_stt_error(turn_context, error_msg)
                return None

        except Exception as e:
            print(f"❌ Audio processing error: {e}")
            await self._send_audio_response(turn_context, "Fehler beim Verarbeiten der Sprache.")
            return None

    async def _download_audio(self, attachment: Attachment) -> Optional[bytes]:
        """Download audio from attachment"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.content_url) as response:
                    if response.status == 200:
                        audio_bytes = await response.read()
                        if len(audio_bytes) < 100:
                            print(f"❌ Audio file too small: {len(audio_bytes)} bytes")
                            return None
                        return audio_bytes
                    else:
                        print(f"❌ HTTP error: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ Audio download error: {e}")
            return None

    async def _convert_audio(self, audio_bytes: bytes, content_type: str) -> Optional[bytes]:
        """Convert audio to Azure-compatible format"""
        try:
            # Check if already compatible
            if content_type in {'audio/wav', 'audio/x-wav', 'audio/wave'}:
                if self._validate_wav_header(audio_bytes):
                    return audio_bytes

            # Use FFmpeg converter
            if hasattr(self.audio_converter, 'convert_to_azure_wav'):
                return await self.audio_converter.convert_to_azure_wav(audio_bytes)

            return None
        except Exception as e:
            print(f"❌ Audio conversion error: {e}")
            return None

    def _validate_wav_header(self, audio_bytes: bytes) -> bool:
        """Validate WAV file header"""
        if len(audio_bytes) < 44:
            return False
        return audio_bytes[:4] == b'RIFF' and audio_bytes[8:12] == b'WAVE'

    # === CLU INTEGRATION ===

    async def _extract_entity_with_clu(self, user_input: str, entity_type: str) -> Optional[str]:
        """Extract specific entity using CLU service"""
        if not self.clu_service:
            print("⚠️ CLU service not available")
            return None

        try:
            entities = await self.clu_service.get_entities(text=user_input)
            print(f"🔍 CLU entities for {entity_type}: {entities}")

            for entity in entities:
                entity_name = entity.get('category', '') or entity.get('name', '')
                entity_text = entity.get('text', '')

                if entity_name == entity_type:
                    print(f"✅ {entity_type} found: '{entity_text}'")
                    return entity_text

            print(f"❌ No {entity_type} entity found")
            return None

        except Exception as e:
            print(f"❌ CLU extraction error for {entity_type}: {e}")
            return None

    async def _extract_confirmation_with_clu(self, user_input: str) -> Optional[str]:
        """Extract confirmation response using CLU (yes/no)"""
        if not self.clu_service:
            print("⚠️ CLU service not available for confirmation")
            return None

        try:
            entities = await self.clu_service.get_entities(text=user_input)
            print(f"🔍 CLU entities for confirmation: {entities}")

            # Look for ConfirmationAnswer entity
            for entity in entities:
                entity_category = entity.get('category', '') or entity.get('name', '')
                entity_key = entity.get('key', '')
                entity_text = entity.get('text', '')

                if entity_category == 'ConfirmationAnswer':
                    print(f"✅ ConfirmationAnswer found: key='{entity_key}', text='{entity_text}'")
                    return entity_key.lower()  # Return 'yes' or 'no'

            print("❌ No ConfirmationAnswer entity found")
            return None

        except Exception as e:
            print(f"❌ CLU confirmation extraction error: {e}")
            return None

    # === AUDIO OUTPUT ===

    def _convert_markdown_to_speech(self, text: str) -> str:
        """Konvertiert Markdown zu sprachfreundlichem Text"""
        speech_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** -> bold
        speech_text = re.sub(r'\*([^*]+)\*', r'\1', speech_text)  # *italic* -> italic
        speech_text = re.sub(r'•\s*', '', speech_text)  # Bullet points entfernen
        speech_text = re.sub(r'\n+', ' ', speech_text)  # Zeilenumbrüche zu Leerzeichen
        speech_text = re.sub(r'\s+', ' ', speech_text)  # Mehrfache Leerzeichen entfernen
        return speech_text.strip()

    # 2. FEHLENDE _send_short_text_fallback METHODE
    async def _send_short_text_fallback(self, turn_context: TurnContext, text: str):
        """
        Sehr kurzer Text-Fallback ohne problematische Entities.
        """
        try:
            # Text drastisch kürzen und Sonderzeichen entfernen
            clean_text = text.replace('[', '').replace(']', '').replace('(', '').replace(')', '')
            clean_text = re.sub(r'[^\w\s\.\,\!\?\-]', '', clean_text)  # Nur sichere Zeichen

            if len(clean_text) > 100:
                clean_text = clean_text[:97] + "..."

            fallback_message = f"🔊 {clean_text}"
            await turn_context.send_activity(MessageFactory.text(fallback_message))
            print(f"📝 Text-Fallback gesendet: {len(fallback_message)} Zeichen")
        except Exception as e:
            print(f"❌ Text-Fallback fehlgeschlagen: {e}")
            try:
                await turn_context.send_activity(MessageFactory.text("🔊 Audio-Fehler"))
            except:
                print("❌ Kompletter Kommunikationsfehler")

    # 3. FEHLENDE _compress_for_bot_framework METHODE
    async def _compress_for_bot_framework(self, audio_bytes: bytes) -> bytes:
        """
        Aggressive Kompression speziell für Bot Framework 256KB Limit
        """
        try:
            import tempfile
            import subprocess
            import os

            if not hasattr(self.audio_converter, 'ffmpeg_available') or not self.audio_converter.ffmpeg_available:
                print("⚠️ FFmpeg nicht verfügbar - keine Kompression möglich")
                return None

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
                input_file.write(audio_bytes)
                input_file.flush()

                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as output_file:
                    try:
                        # Sehr aggressive Kompression für Bot Framework
                        cmd = [
                            'ffmpeg', '-y', '-i', input_file.name,
                            '-acodec', 'libmp3lame',
                            '-b:a', '48k',  # Sehr niedrige Bitrate
                            '-ac', '1',  # Mono
                            '-ar', '22050',  # Niedrige Samplingrate
                            '-q:a', '7',  # Niedrige Qualität aber verständlich
                            '-f', 'mp3',
                            output_file.name
                        ]

                        result = subprocess.run(cmd, capture_output=True, timeout=30)

                        if result.returncode == 0:
                            with open(output_file.name, 'rb') as f:
                                compressed_data = f.read()

                            compression_ratio = len(compressed_data) / len(audio_bytes) * 100
                            print(
                                f"🎵 Bot Framework Kompression: {len(audio_bytes)} → {len(compressed_data)} bytes ({compression_ratio:.1f}%)")

                            return compressed_data
                        else:
                            print(f"❌ FFmpeg Kompression fehlgeschlagen: {result.stderr}")
                            return None

                    finally:
                        try:
                            os.unlink(output_file.name)
                        except:
                            pass

            try:
                os.unlink(input_file.name)
            except:
                pass

        except Exception as e:
            print(f"❌ Bot Framework Kompression fehlgeschlagen: {e}")
            return None

    # 4. FEHLENDE _send_chunked_audio_small METHODE
    async def _send_chunked_audio_small(self, turn_context: TurnContext, text: str):
        """
        Teilt Text in sehr kleine Chunks für Bot Framework Limits
        """
        try:
            # Sehr kleine Chunks (50 Zeichen) um unter 256KB zu bleiben
            chunks = self._split_text_for_tts(text, max_length=50)

            success_count = 0

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                try:
                    # TTS für kleinen Chunk
                    audio_bytes = self.speech_service.text_to_speech_bytes(chunk.strip())

                    if audio_bytes and len(audio_bytes) <= 200000:  # 200KB sicher unter Limit
                        await self._send_audio_file_direct(turn_context, audio_bytes)
                        success_count += 1

                        # Pause zwischen Chunks
                        if i < len(chunks) - 1:
                            import asyncio
                            await asyncio.sleep(0.8)
                    else:
                        print(f"⚠️ Auch Chunk {i + 1} zu groß ({len(audio_bytes) if audio_bytes else 0} bytes)")
                        await self._send_short_text_fallback(turn_context, chunk)

                except Exception as chunk_error:
                    print(f"❌ Chunk {i + 1} Fehler: {chunk_error}")
                    await self._send_short_text_fallback(turn_context, chunk)

            print(f"✅ Chunked Audio: {success_count}/{len(chunks)} Chunks erfolgreich gesendet")

        except Exception as e:
            print(f"❌ Chunked Audio Fehler: {e}")
            await self._send_short_text_fallback(turn_context, text)

    # 5. FEHLENDE _send_audio_file_direct METHODE
    async def _send_audio_file_direct(self, turn_context: TurnContext, audio_bytes: bytes):
        """
        Sendet Audio-Bytes direkt als Datei (muss unter 256KB sein)
        """
        try:
            import tempfile
            import os

            # Doppelt prüfen
            if len(audio_bytes) > 250000:
                print(f"❌ Audio immer noch zu groß: {len(audio_bytes)} bytes")
                await self._send_short_text_fallback(turn_context, "Audio zu groß für Übertragung")
                return

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file.flush()

                try:
                    with open(temp_file.name, 'rb') as audio_file:
                        audio_data = audio_file.read()

                    attachment = Attachment(
                        content_type="audio/wav",
                        content=audio_data,
                        name="bot_response.wav"
                    )

                    reply = MessageFactory.attachment(attachment)
                    await turn_context.send_activity(reply)
                    print(f"✅ Audio-Datei direkt gesendet ({len(audio_bytes)} bytes)")

                finally:
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass

        except Exception as e:
            print(f"❌ Direkte Audio-Übertragung fehlgeschlagen: {e}")
            await self._send_short_text_fallback(turn_context, "Audio-Upload fehlgeschlagen")

    # 6. FEHLENDE _split_text_for_tts METHODE
    def _split_text_for_tts(self, text: str, max_length: int = 50) -> list[str]:
        """
        Teilt Text in sehr kleine Chunks für Bot Framework Limits
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining_text = text

        while remaining_text:
            if len(remaining_text) <= max_length:
                chunks.append(remaining_text.strip())
                break

            # Suche nach Satzende oder Leerzeichen
            chunk = remaining_text[:max_length]
            last_period = chunk.rfind('. ')
            last_space = chunk.rfind(' ')

            if last_period > max_length * 0.6:
                split_pos = last_period + 1
            elif last_space > max_length * 0.7:
                split_pos = last_space
            else:
                split_pos = max_length

            chunk = remaining_text[:split_pos].strip()
            if chunk:
                chunks.append(chunk)

            remaining_text = remaining_text[split_pos:].strip()

        print(f"📝 Text in {len(chunks)} sehr kleine Chunks aufgeteilt ({max_length} Zeichen max)")
        return chunks

    async def _send_audio_response(self, turn_context: TurnContext, text: str):
        """
        Verbesserte Audio-Response mit Azure Blob Storage und robusten Fallbacks
        """
        try:
            print(f"🔊 Generiere Audio für: '{text[:100]}{'...' if len(text) > 100 else ''}'")

            # Text für Sprache optimieren
            speech_text = self._convert_markdown_to_speech(text)

            # TTS generieren
            if not self.speech_service:
                await self._send_short_text_fallback(turn_context, text)
                return

            audio_bytes = self.speech_service.text_to_speech_bytes(speech_text)

            if not audio_bytes or len(audio_bytes) == 0:
                await self._send_short_text_fallback(turn_context, text)
                return

            print(f"🎵 Audio generiert: {len(audio_bytes)} bytes")

            # Strategie 1: Azure Blob Storage (für große Dateien)
            if hasattr(self, 'audio_blob_uploader') and self.audio_blob_uploader.blob_service_client:
                try:
                    await self._send_audio_via_blob(turn_context, audio_bytes)
                    return
                except Exception as e:
                    print(f"⚠️ Blob Upload fehlgeschlagen: {e} - versuche Fallback")

            # Strategie 2: Direkte Übertragung (wenn unter Bot Framework Limit)
            BOT_FRAMEWORK_LIMIT = 250000  # 250KB
            if len(audio_bytes) <= BOT_FRAMEWORK_LIMIT:
                try:
                    await self._send_audio_file_direct(turn_context, audio_bytes)
                    return
                except Exception as e:
                    print(f"⚠️ Direkte Übertragung fehlgeschlagen: {e}")

            # Strategie 3: Kompression versuchen
            try:
                compressed = await self._compress_for_bot_framework(audio_bytes)
                if compressed and len(compressed) <= BOT_FRAMEWORK_LIMIT:
                    await self._send_audio_file_direct(turn_context, compressed)
                    return
            except Exception as e:
                print(f"⚠️ Kompression fehlgeschlagen: {e}")

            # Strategie 4: Text-Chunking als letzter Ausweg
            print("⚠️ Alle Audio-Strategien fehlgeschlagen - verwende Text-Chunks")
            await self._send_chunked_audio_small(turn_context, speech_text)

        except Exception as e:
            print(f"❌ Kompletter Audio-Fehler: {e}")
            await self._send_short_text_fallback(turn_context, text)

    async def _send_audio_via_blob_improved(self, turn_context: TurnContext, audio_bytes: bytes):
        """
        Verbesserte Azure Blob Upload Methode
        """
        try:
            # Optional: Komprimiere für bessere Performance
            final_audio = audio_bytes
            content_type = "audio/wav"

            if hasattr(self, '_compress_audio_for_blob'):
                compressed_audio = await self._compress_audio_for_blob(audio_bytes)
                if compressed_audio and len(compressed_audio) < len(audio_bytes) * 0.8:
                    final_audio = compressed_audio
                    content_type = "audio/mp3"
                    print(f"📦 Kompression: {len(audio_bytes)} → {len(compressed_audio)} bytes")

            # Upload zu Azure Blob
            blob_url = await self.audio_blob_uploader.upload_audio_blob(final_audio, content_type)

            if blob_url:
                # Sende Attachment mit Blob URL
                attachment = Attachment(
                    content_type=content_type,
                    content_url=blob_url,
                    name="bot_response.mp3" if content_type == "audio/mp3" else "bot_response.wav"
                )

                reply = MessageFactory.attachment(attachment)
                await turn_context.send_activity(reply)
                print(f"✅ Audio via Azure Blob gesendet ({len(final_audio)} bytes)")
            else:
                raise Exception("Blob Upload returned no URL")

        except Exception as e:
            print(f"❌ Blob Audio-Upload fehlgeschlagen: {e}")
            raise

    async def _send_audio_fallback(self, turn_context: TurnContext, audio_bytes: bytes, original_text: str):
        """
        Fallback wenn Azure Blob nicht verfügbar
        """
        try:
            print("⚠️ Azure Blob nicht verfügbar - verwende lokale Strategien")

            # Versuche aggressive Kompression für Bot Framework Limit
            compressed = await self._compress_for_bot_framework(audio_bytes)

            if compressed and len(compressed) <= 250000:
                # Direkte Übertragung möglich
                attachment = Attachment(
                    content_type="audio/mp3",
                    content=compressed,
                    name="bot_response.mp3"
                )
                reply = MessageFactory.attachment(attachment)
                await turn_context.send_activity(reply)
                print(f"✅ Komprimiertes Audio direkt gesendet ({len(compressed)} bytes)")
            else:
                # Text-Chunking als letzter Ausweg
                await self._send_chunked_audio_small(turn_context, original_text)

        except Exception as e:
            print(f"❌ Audio-Fallback fehlgeschlagen: {e}")
            await self._send_short_text_fallback(turn_context, original_text)

    async def _compress_audio_for_blob(self, audio_bytes: bytes) -> bytes:
        """
        Moderate Kompression für Blob Storage (bessere Qualität da kein Bot Framework Limit)
        """
        try:
            if not hasattr(self.audio_converter, 'ffmpeg_available') or not self.audio_converter.ffmpeg_available:
                return None

            # Moderate Kompression für Blob (96kbps, Mono)
            if hasattr(self, '_compress_to_mp3_method'):
                compressed = await self._compress_to_mp3_method(
                    audio_bytes,
                    bitrate="96k",
                    channels=1,
                    sample_rate=22050
                )
                return compressed

            return None

        except Exception as e:
            print(f"❌ Blob-Kompression fehlgeschlagen: {e}")
            return None


    async def _send_audio_and_text_response(self, turn_context: TurnContext, text: str):
        """Send both audio and text response for maximum accessibility"""
        try:
            # Send text first for immediate feedback
            await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))

            # Then try to send audio
            if self.speech_service:
                speech_text = self._convert_text_for_speech(text)
                audio_bytes = self.speech_service.text_to_speech_bytes(speech_text)

                if audio_bytes and len(audio_bytes) <= 250000:
                    await self._send_audio_with_fallback(turn_context, audio_bytes)
                elif audio_bytes:
                    # If too large, send chunked
                    await self._send_chunked_audio(turn_context, speech_text)

        except Exception as e:
            print(f"❌ Audio+Text response error: {e}")

    async def _send_audio_with_fallback(self, turn_context: TurnContext, audio_bytes: bytes) -> bool:
        """Try multiple methods to send audio"""

        # Method 1: Try as Media Attachment (best for Telegram)
        try:
            success = await self._send_audio_as_media(turn_context, audio_bytes)
            if success:
                print(f"✅ Audio sent as media: {len(audio_bytes)} bytes")
                return True
        except Exception as e:
            print(f"⚠️ Media attachment failed: {e}")

        # Method 2: Try as Base64 Data URL
        try:
            success = await self._send_audio_as_base64(turn_context, audio_bytes)
            if success:
                print(f"✅ Audio sent as base64: {len(audio_bytes)} bytes")
                return True
        except Exception as e:
            print(f"⚠️ Base64 attachment failed: {e}")

        # Method 3: Try as File Attachment
        try:
            success = await self._send_audio_as_file(turn_context, audio_bytes)
            if success:
                print(f"✅ Audio sent as file: {len(audio_bytes)} bytes")
                return True
        except Exception as e:
            print(f"⚠️ File attachment failed: {e}")

        return False

    async def _send_audio_as_media(self, turn_context: TurnContext, audio_bytes: bytes) -> bool:
        """Send audio as media attachment (preferred for Telegram)"""
        try:
            import tempfile
            import os

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                # Convert to OGG for better Telegram compatibility if FFmpeg available
                if hasattr(self.audio_converter, 'convert_to_ogg') and self.audio_converter.ffmpeg_available:
                    try:
                        ogg_bytes = await self.audio_converter.convert_to_ogg(audio_bytes)
                        if ogg_bytes:
                            temp_file.write(ogg_bytes)
                            content_type = "audio/ogg"
                        else:
                            temp_file.write(audio_bytes)
                            content_type = "audio/wav"
                    except:
                        temp_file.write(audio_bytes)
                        content_type = "audio/wav"
                else:
                    temp_file.write(audio_bytes)
                    content_type = "audio/wav"

                temp_file.flush()

                try:
                    # Read file for attachment
                    with open(temp_file.name, 'rb') as audio_file:
                        file_data = audio_file.read()

                    # Create media attachment
                    attachment = Attachment(
                        content_type=content_type,
                        content=file_data,
                        name="voice_message.ogg" if content_type == "audio/ogg" else "voice_message.wav"
                    )

                    # Send as media
                    reply = MessageFactory.attachment(attachment)
                    await turn_context.send_activity(reply)
                    return True

                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass

        except Exception as e:
            print(f"❌ Media attachment error: {e}")
            return False

    async def _send_audio_as_base64(self, turn_context: TurnContext, audio_bytes: bytes) -> bool:
        """Send audio as base64 data URL"""
        try:
            # Convert to base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            # Create data URL attachment
            attachment = Attachment(
                content_type="audio/wav",
                content_url=f"data:audio/wav;base64,{audio_base64}",
                name="voice_response.wav"
            )

            reply = MessageFactory.attachment(attachment)
            await turn_context.send_activity(reply)
            return True

        except Exception as e:
            print(f"❌ Base64 attachment error: {e}")
            return False

    async def _send_audio_as_file(self, turn_context: TurnContext, audio_bytes: bytes) -> bool:
        """Send audio as regular file attachment"""
        try:
            attachment = Attachment(
                content_type="audio/wav",
                content=audio_bytes,
                name="response.wav"
            )
            reply = MessageFactory.attachment(attachment)
            await turn_context.send_activity(reply)
            return True

        except Exception as e:
            print(f"❌ File attachment error: {e}")
            return False

    async def _send_chunked_audio(self, turn_context: TurnContext, text: str):
        """Send large text as multiple smaller audio files"""
        chunks = self._split_text_for_audio(text, max_length=100)

        for i, chunk in enumerate(chunks):
            try:
                audio_bytes = self.speech_service.text_to_speech_bytes(chunk)
                if audio_bytes and len(audio_bytes) <= 250000:
                    # Try multiple attachment methods for each chunk
                    success = await self._send_audio_with_fallback(turn_context, audio_bytes)
                    if not success:
                        await turn_context.send_activity(MessageFactory.text(f"🔊 Teil {i + 1}: {chunk}"))
                else:
                    await turn_context.send_activity(MessageFactory.text(f"🔊 Teil {i + 1}: {chunk}"))
            except Exception as e:
                print(f"❌ Chunk {i + 1} error: {e}")
                await turn_context.send_activity(MessageFactory.text(f"🔊 Teil {i + 1}: {chunk}"))

    def _split_text_for_audio(self, text: str, max_length: int = 100) -> List[str]:
        """Split text into chunks suitable for audio"""
        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining.strip())
                break

            # Find good split point
            chunk = remaining[:max_length]
            split_pos = chunk.rfind('. ')
            if split_pos < max_length * 0.7:
                split_pos = chunk.rfind(' ')
            if split_pos < max_length * 0.5:
                split_pos = max_length

            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()

        return chunks

    def _convert_text_for_speech(self, text: str) -> str:
        """Convert text to speech-friendly format"""
        # Remove markdown
        speech_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        speech_text = re.sub(r'\*([^*]+)\*', r'\1', speech_text)
        speech_text = re.sub(r'•\s*', '', speech_text)
        speech_text = re.sub(r'\n+', ' ', speech_text)
        speech_text = re.sub(r'\s+', ' ', speech_text)
        return speech_text.strip()

    # === DIALOG HANDLERS WITH CLU INTEGRATION ===

    async def _handle_greeting(self, turn_context: TurnContext, user_profile, *args):
        """Handle greeting"""
        await self._send_audio_response(turn_context, SpeechBotMessages.WELCOME_MESSAGE)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CONSENT)

    async def _handle_consent_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle consent with CLU integration"""

        # Try CLU confirmation extraction first
        clu_confirmation = await self._extract_confirmation_with_clu(user_input)

        consent_given = False
        consent_denied = False

        if clu_confirmation:
            # Use CLU result
            consent_given = clu_confirmation == 'yes'
            consent_denied = clu_confirmation == 'no'
            print(f"🔍 CLU consent: {clu_confirmation} -> given={consent_given}, denied={consent_denied}")
        else:
            # Fallback to manual detection
            user_input_lower = user_input.lower().strip()
            consent_given = any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES)
            consent_denied = any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES)
            print(f"🔄 Manual consent: '{user_input_lower}' -> given={consent_given}, denied={consent_denied}")

        if consent_given:
            await self._send_audio_response(turn_context, SpeechBotMessages.CONSENT_GRANTED)
            user_profile['consent_given'] = True
            user_profile['consent_timestamp'] = datetime.now().isoformat()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._ask_for_gender(turn_context)

        elif consent_denied:
            await self._send_audio_response(turn_context, SpeechBotMessages.CONSENT_DENIED)
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
            await self.user_profile_accessor.set(turn_context, {
                'consent_given': False,
                'consent_timestamp': datetime.now().isoformat(),
                'registration_cancelled': True
            })
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.CONSENT_UNCLEAR)

    async def _ask_for_gender(self, turn_context: TurnContext):
        """Ask for gender"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['gender'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_GENDER)

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle gender input with CLU"""
        # Try CLU extraction first
        gender_entity = await self._extract_entity_with_clu(user_input, 'Gender')

        # Use CLU result or fallback to direct matching
        input_to_check = gender_entity.lower() if gender_entity else user_input.lower()

        if input_to_check in FieldConfig.GENDER_OPTIONS:
            gender_value, gender_display = FieldConfig.GENDER_OPTIONS[input_to_check]
            user_profile['gender'] = gender_value
            user_profile['gender_display'] = gender_display
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'gender', 'Geschlecht', gender_display):
                return

            await self._confirm_field(turn_context, "Geschlecht", gender_display,
                                      DialogState.CONFIRM_PREFIX + "gender")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['gender'])

    async def _ask_for_title(self, turn_context: TurnContext):
        """Ask for title"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['title'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_TITLE)

    async def _handle_title_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle title input with CLU"""
        # Try CLU extraction
        title_entity = await self._extract_entity_with_clu(user_input, 'Title')

        user_input_lower = (title_entity or user_input).strip().lower()

        if user_input_lower in FieldConfig.NO_TITLE_KEYWORDS:
            user_profile['title'] = ''
            user_profile['title_display'] = "Kein Titel"
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'title', 'Titel', "Kein Titel"):
                return

            await self._confirm_field(turn_context, "Titel", "Kein Titel",
                                      DialogState.CONFIRM_PREFIX + "title")
        elif (title_entity or user_input) in FieldConfig.VALID_TITLES:
            title_value = title_entity or user_input
            user_profile['title'] = title_value
            user_profile['title_display'] = title_value
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'title', 'Titel', title_value):
                return

            await self._confirm_field(turn_context, "Titel", title_value,
                                      DialogState.CONFIRM_PREFIX + "title")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['title'])

    async def _ask_for_first_name(self, turn_context: TurnContext):
        """Ask for first name"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['first_name'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_FIRST_NAME)

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle first name input with CLU"""
        # Try CLU extraction first
        name_entity = await self._extract_entity_with_clu(user_input, 'Name')

        name_to_validate = name_entity if name_entity and DataValidator.validate_name_part(name_entity) else user_input

        if DataValidator.validate_name_part(name_to_validate):
            user_profile['first_name'] = name_to_validate.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'first_name', 'Vorname', name_to_validate):
                return

            await self._confirm_field(turn_context, "Vorname", name_to_validate,
                                      DialogState.CONFIRM_PREFIX + "first_name")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['first_name'])

    async def _ask_for_last_name(self, turn_context: TurnContext):
        """Ask for last name"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['last_name'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_LAST_NAME)

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle last name input with CLU"""
        # Try CLU extraction first
        name_entity = await self._extract_entity_with_clu(user_input, 'Name')

        name_to_validate = name_entity if name_entity and DataValidator.validate_name_part(name_entity) else user_input

        if DataValidator.validate_name_part(name_to_validate):
            user_profile['last_name'] = name_to_validate.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'last_name', 'Nachname', name_to_validate):
                return

            await self._confirm_field(turn_context, "Nachname", name_to_validate,
                                      DialogState.CONFIRM_PREFIX + "last_name")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['last_name'])

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        """Ask for birthdate"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['birthdate'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle birthdate input with CLU"""
        # Try CLU extraction first
        date_entity = await self._extract_entity_with_clu(user_input, 'DateOfBirth')

        # Try validation with CLU result first, then fallback to original input
        birthdate = None
        display_date = None

        if date_entity:
            birthdate = DataValidator.validate_birthdate(date_entity)
            if birthdate:
                display_date = date_entity

        if not birthdate:
            birthdate = DataValidator.validate_birthdate(user_input)
            if birthdate:
                display_date = user_input

        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = display_date
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'birth_date', 'Geburtsdatum', display_date):
                return

            await self._confirm_field(turn_context, "Geburtsdatum", display_date,
                                      DialogState.CONFIRM_PREFIX + "birthdate")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['birthdate'])

    async def _ask_for_email(self, turn_context: TurnContext):
        """Ask for email"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['email'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle email input with CLU"""
        # Try CLU extraction first
        email_entity = await self._extract_entity_with_clu(user_input, 'email')

        # Try validation with CLU result first, then fallback
        email_to_validate = email_entity if email_entity and DataValidator.validate_email(email_entity) else user_input

        if DataValidator.validate_email(email_to_validate):
            if not user_profile.get('correction_mode'):
                if await self.customer_service.email_exists_in_db(email_to_validate.strip().lower()):
                    await self._send_audio_response(turn_context,
                                                    SpeechBotMessages.VALIDATION_ERRORS['email_exists'])
                    return

            user_profile['email'] = email_to_validate.strip().lower()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'email', 'E-Mail', email_to_validate):
                return

            await self._confirm_field(turn_context, "E-Mail", email_to_validate,
                                      DialogState.CONFIRM_PREFIX + "email")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['email'])

    async def _ask_for_phone(self, turn_context: TurnContext):
        """Ask for phone"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['phone'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_PHONE)

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle phone input with CLU"""
        # Try CLU extraction first
        phone_entity = await self._extract_entity_with_clu(user_input, 'PhoneNumber')

        phone_to_validate = phone_entity or user_input
        phone_number_obj = DataValidator.validate_phone(phone_to_validate)

        if phone_number_obj:
            user_profile['telephone'] = phone_number_obj.as_e164
            user_profile['telephone_display'] = phone_to_validate
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'telephone', 'Telefonnummer', phone_to_validate):
                return

            await self._confirm_field(turn_context, "Telefonnummer", phone_to_validate,
                                      DialogState.CONFIRM_PREFIX + "phone")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['phone'])

    async def _ask_for_street(self, turn_context: TurnContext):
        """Ask for street"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['street'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_STREET)

    async def _handle_street_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle street input with CLU"""
        # Try CLU extraction first
        street_entity = await self._extract_entity_with_clu(user_input, 'StreetHousenumber')

        if street_entity:
            # Extract street name from StreetHousenumber entity
            street_name = re.sub(r'\s*\d+[a-zA-Z]*\s*', street_entity).strip()

            if len(street_name) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', street_name):
                user_profile['street_name'] = street_name

            # Also extract house number if not already set
            numbers = re.findall(r'\d+', street_entity)
            if numbers and not user_profile.get('house_number'):
                try:
                    house_number = int(numbers[-1])
                    if house_number > 0:
                        user_profile['house_number'] = house_number
                except ValueError:
                    pass

            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'street_name', 'Straße', street_name):
                return

            await self._confirm_field(turn_context, "Straße", street_name,
                                      DialogState.CONFIRM_PREFIX + "street")
            return

        # Fallback to direct validation
        if len(user_input.strip()) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', user_input.strip()):
            user_profile['street_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
            'street_name', 'Straße', user_input):
                return

            await self._confirm_field(turn_context, "Straße", user_input,
                                  DialogState.CONFIRM_PREFIX + "street")

        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['street'])


    async def _ask_for_house_number(self, turn_context: TurnContext):
        """Ask for house number"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['house_number'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_NUMBER)


    async def _handle_house_number_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle house number input with CLU"""
        # Try CLU extraction first
        house_entity = await self._extract_entity_with_clu(user_input, 'houseNumber')

        house_number = None

        if house_entity:
            # Extract numbers from house number entity
            numbers = re.findall(r'\d+', house_entity)
            if numbers:
                try:
                    house_number = int(numbers[-1])
                except ValueError:
                    pass

        if not house_number:
            # Fallback to direct parsing
            try:
                house_number = int(user_input.strip())
            except ValueError:
                pass

        if house_number and house_number > 0:
            user_profile['house_number'] = house_number
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'house_number', 'Hausnummer', str(house_number)):
                return

            await self._confirm_field(turn_context, "Hausnummer", str(house_number),
                                      DialogState.CONFIRM_PREFIX + "house_number")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['house_number'])


    async def _ask_for_house_addition(self, turn_context: TurnContext):
        """Ask for house addition"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['house_addition'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_ADDITION)


    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle house addition input"""
        if user_input.lower() in FieldConfig.NO_ADDITION_KEYWORDS:
            user_profile['house_number_addition'] = ""
            user_profile['house_addition_display'] = "Kein Zusatz"
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'house_number_addition', 'Hausnummernzusatz', "Kein Zusatz"):
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
        """Ask for postal code"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['postal'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_POSTAL)


    async def _handle_postal_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle postal code input with CLU"""
        # Try CLU extraction first
        zip_entity = await self._extract_entity_with_clu(user_input, 'ZipCode')

        postal_to_validate = zip_entity or user_input
        validated_postal = DataValidator.validate_postal_code(postal_to_validate)

        if not validated_postal:
            # Try enhanced validation
            validated_postal = DataValidator.validate_postal_code_enhanced(postal_to_validate)

        if validated_postal:
            user_profile['postal_code'] = validated_postal
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'postal_code', 'Postleitzahl', validated_postal):
                return

            await self._confirm_field(turn_context, "Postleitzahl", validated_postal,
                                      DialogState.CONFIRM_PREFIX + "postal")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['postal'])


    async def _ask_for_city(self, turn_context: TurnContext):
        """Ask for city"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['city'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CITY)


    async def _handle_city_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle city input with CLU"""
        # Try CLU extraction first
        city_entity = await self._extract_entity_with_clu(user_input, 'City')

        city_to_validate = city_entity or user_input

        if len(city_to_validate.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', city_to_validate.strip()):
            user_profile['city'] = city_to_validate.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'city', 'Ort', city_to_validate):
                return

            await self._confirm_field(turn_context, "Ort", city_to_validate,
                                      DialogState.CONFIRM_PREFIX + "city")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['city'])


    async def _ask_for_country(self, turn_context: TurnContext):
        """Ask for country"""
        await self._send_audio_response(turn_context, SpeechBotMessages.FIELD_PROMPTS['country'])
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_COUNTRY)


    async def _handle_country_input(self, turn_context: TurnContext, user_profile, user_input):
        """Handle country input with CLU"""
        # Try CLU extraction first
        country_entity = await self._extract_entity_with_clu(user_input, 'countryName')

        country_to_validate = country_entity or user_input

        if len(country_to_validate.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', country_to_validate.strip()):
            user_profile['country_name'] = country_to_validate.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'country_name', 'Land', country_to_validate):
                return

            await self._confirm_field(turn_context, "Land", country_to_validate,
                                      DialogState.CONFIRM_PREFIX + "country")
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.VALIDATION_ERRORS['country'])


    # === CONFIRMATION AND FINAL HANDLING ===

    async def _confirm_field(self, turn_context: TurnContext, field_name: str, value: str, confirmation_state: str):
        """Send field confirmation"""
        confirmation_message = SpeechBotMessages.confirmation_prompt(field_name, value)
        await self._send_audio_response(turn_context, confirmation_message)
        await self.dialog_state_accessor.set(turn_context, confirmation_state)

    async def _handle_confirmation(self, turn_context: TurnContext, user_profile, user_input, dialog_state):
        """Handle confirmation responses with CLU integration"""

        # Try CLU confirmation extraction first
        clu_confirmation = await self._extract_confirmation_with_clu(user_input)

        confirmed = False
        rejected = False

        if clu_confirmation:
            # Use CLU result
            confirmed = clu_confirmation == 'yes'
            rejected = clu_confirmation == 'no'
            print(f"🔍 CLU confirmation: {clu_confirmation} -> confirmed={confirmed}, rejected={rejected}")
        else:
            # Fallback to manual detection
            user_input_lower = user_input.lower()
            confirmed = user_input_lower in FieldConfig.CONFIRMATION_YES
            rejected = user_input_lower in FieldConfig.CONFIRMATION_NO
            print(f"🔄 Manual confirmation: '{user_input_lower}' -> confirmed={confirmed}, rejected={rejected}")

        if confirmed:
            # Find next step in dialog flow
            found_next_step = False
            for conf_state, next_ask_func, _ in self.dialog_flow:
                if dialog_state == conf_state:
                    await next_ask_func(turn_context)
                    found_next_step = True
                    break

            if not found_next_step and dialog_state == DialogState.CONFIRM_PREFIX + "country":
                await self._show_final_summary(turn_context)

        elif rejected:
            # Find correction step
            found_correction_step = False
            for conf_state, _, correction_ask_func in self.dialog_flow:
                if dialog_state == conf_state:
                    await self._send_audio_response(turn_context, SpeechBotMessages.CONFIRMATION_REJECTED)
                    await correction_ask_func(turn_context)
                    found_correction_step = True
                    break

            if not found_correction_step:
                await self._send_audio_response(turn_context,
                                                "Entschuldigung, ich kann diesen Schritt nicht korrigieren.")
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        else:
            # Neither confirmed nor rejected - ask for clarification
            await self._send_audio_response(turn_context, SpeechBotMessages.CONFIRMATION_UNCLEAR)


    async def _show_final_summary(self, turn_context: TurnContext):
        """Show final summary"""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        summary_message = SpeechBotMessages.final_summary(user_profile)
        await self._send_audio_response(turn_context, summary_message)
        await self.dialog_state_accessor.set(turn_context, DialogState.FINAL_CONFIRMATION)

    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """Handle final confirmation with CLU integration"""

        # Try CLU confirmation extraction first
        clu_confirmation = await self._extract_confirmation_with_clu(user_input)

        save_data = False
        start_correction = False
        restart_requested = False

        if clu_confirmation:
            # Use CLU result
            save_data = clu_confirmation == 'yes'
            start_correction = clu_confirmation == 'no'
            print(f"🔍 CLU final confirmation: {clu_confirmation} -> save={save_data}, correct={start_correction}")
        else:
            # Fallback to manual detection
            user_input_lower = user_input.lower().strip()
            save_data = any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES)
            start_correction = any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES)
            restart_requested = any(response in user_input_lower for response in FieldConfig.RESTART_KEYWORDS)
            print(
                f"🔄 Manual final confirmation: save={save_data}, correct={start_correction}, restart={restart_requested}")

        if save_data:
            # Save data
            await self._send_audio_response(turn_context, SpeechBotMessages.SAVE_IN_PROGRESS)

            success = await self._save_customer_data(user_profile)

            if success:
                await self._send_audio_response(turn_context, SpeechBotMessages.REGISTRATION_SUCCESS)
                await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
                await self.user_profile_accessor.set(turn_context, {
                    'registration_completed': True,
                    'completion_timestamp': datetime.now().isoformat()
                })
            else:
                await self._send_audio_response(turn_context, SpeechBotMessages.SAVE_ERROR)
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)

        elif start_correction:
            # Start correction process
            await self._start_correction_process(turn_context, user_profile)

        elif restart_requested:
            # Complete restart
            await self._handle_restart_request(turn_context)

        else:
            # Unclear answer
            await self._send_audio_response(turn_context, SpeechBotMessages.FINAL_CONFIRMATION_UNCLEAR)


    # === CORRECTION HANDLING ===

    async def _start_correction_process(self, turn_context: TurnContext, user_profile):
        """Start correction process"""
        await self._send_audio_response(turn_context, SpeechBotMessages.CORRECTION_OPTIONS)
        await self.dialog_state_accessor.set(turn_context, "correction_selection")


    async def _handle_correction_selection(self, turn_context: TurnContext, user_profile, user_input):
        """Handle correction selection"""
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

            correction_message = SpeechBotMessages.correction_start(field_display)
            await self._send_audio_response(turn_context, correction_message)

            await self.dialog_state_accessor.set(turn_context, target_state)
            user_profile['correction_mode'] = True
            user_profile['correction_return_to'] = 'final_summary'
            await self.user_profile_accessor.set(turn_context, user_profile)

        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.CORRECTION_NOT_UNDERSTOOD)


    async def _check_correction_mode_and_handle(self, turn_context: TurnContext, user_profile,
                                                field_name, field_display, new_value):
        """Handle correction mode"""
        if user_profile.get('correction_mode'):
            correction_message = SpeechBotMessages.correction_success(field_display, new_value)
            await self._send_audio_response(turn_context, correction_message)

            user_profile['correction_mode'] = False
            await self.user_profile_accessor.set(turn_context, user_profile)

            await self._show_final_summary(turn_context)
            return True

        return False


    # === STATE HANDLING ===

    async def _handle_completed_state(self, turn_context: TurnContext, user_profile, user_input):
        """Handle completed state"""
        user_input_lower = user_input.lower()

        if any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            if user_profile.get('registration_cancelled'):
                await self._send_audio_response(turn_context, SpeechBotMessages.RESTART_NEW_REGISTRATION)

                await self.user_profile_accessor.set(turn_context, {})
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                await self._handle_greeting(turn_context, {})

            elif user_profile.get('consent_given') and not user_profile.get('registration_cancelled'):
                await self._send_audio_response(turn_context, SpeechBotMessages.ALREADY_REGISTERED)
        else:
            if user_profile.get('registration_cancelled'):
                await self._send_audio_response(turn_context, SpeechBotMessages.REGISTRATION_CANCELLED_HELP)
            else:
                await self._send_audio_response(turn_context, SpeechBotMessages.ALREADY_COMPLETED_HELP)


    async def _handle_unknown_state(self, turn_context: TurnContext, user_profile, user_input):
        """Handle unknown state"""
        user_input_lower = user_input.lower()

        if any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            await self._send_audio_response(turn_context, SpeechBotMessages.UNKNOWN_STATE_RESTART)

            await self.user_profile_accessor.set(turn_context, {})
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
            await self._handle_greeting(turn_context, {})
        else:
            await self._send_audio_response(turn_context, SpeechBotMessages.UNKNOWN_STATE_CONFUSION)
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)


    async def _handle_restart_request(self, turn_context: TurnContext):
        """Handle restart request"""
        await self._send_audio_response(turn_context, SpeechBotMessages.RESTART_MESSAGE)

        await self.user_profile_accessor.set(turn_context, {})
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
        await self._handle_greeting(turn_context, {})


    # === ERROR HANDLING ===

    async def _handle_stt_error(self, turn_context: TurnContext, error_msg: str):
        """Handle STT errors"""
        error_responses = {
            "invalid_header": "Das Audio-Format konnte nicht verarbeitet werden.",
            "nomatch": "Ich konnte keine Sprache erkennen. Sprechen Sie bitte deutlicher.",
            "canceled": "Die Spracherkennung wurde unterbrochen.",
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
        """Save customer data"""
        try:
            return await self.customer_service.store_data_db(user_profile.copy())
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False


    async def _save_state(self, turn_context: TurnContext):
        """Save bot state"""
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)