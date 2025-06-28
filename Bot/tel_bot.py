import aiohttp
import re
from datetime import datetime
from typing import Dict, Any, Optional
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from phonenumbers import NumberParseException, parse, is_valid_number
from asgiref.sync import sync_to_async
from injector import inject
from Bot.message_bot import DialogState

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount, Attachment, ActivityTypes
from Bot.azure_service.luis_service import  AzureCLUService
from Bot.azure_service.speech_service import AzureSpeechService
from Bot.models import Customer, AddressCountry, AddressStreet, AddressCity, Address, CustomerContact
#
#
# print("=== VEREINFACHTER AUDIO BOT WIRD GELADEN ===")
#
#
# class SimplifiedAudioStates:
#     """Vereinfachte States für den Sprachfluss"""
#     START = "start"
#     ASK_NAME = "ask_name"
#     ASK_BIRTHDATE = "ask_birthdate"
#     ASK_EMAIL = "ask_email"
#     ASK_PHONE = "ask_phone"
#     ASK_ADDRESS = "ask_address"
#     ASK_POSTAL_CITY = "ask_postal_city"
#     ASK_COUNTRY = "ask_country"
#     FINAL_VALIDATION = "final_validation"
#     SAVE_DATA = "save_data"
#     COMPLETED = "completed"
#     ERROR = "error"
#
#
# class AudioBots(ActivityHandler):
#     def __init__(self, conversation_state: ConversationState, user_state: UserState):
#         super().__init__()
#         print("🎤 Initialisiere Vereinfachten Audio Bot...")
#
#         # States
#         self.conversation_state = conversation_state
#         self.user_state = user_state
#
#         # State Accessors
#         self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
#         self.dialog_state_accessor = self.conversation_state.create_property("DialogState")
#
#         # Azure Services initialisieren
#         try:
#             # Importiere deine Settings richtig
#             from FCCSemesterAufgabe.settings import AZURE_KEYVAULT, isDocker
#             self.keyvault = AZURE_KEYVAULT
#
#             if isDocker:
#                 print("⚠️ KeyVault Service nicht verfügbar")
#                 self.clu_service = None
#                 self.speech_service = None
#             else:
#                 self.clu_service = AzureCLUService(self.keyvault)
#                 self.speech_service = AzureSpeechService(self.keyvault)
#                 print("✅ Azure Services erfolgreich initialisiert")
#
#         except Exception as e:
#             print(f"⚠️ Azure Services nicht verfügbar: {e}")
#             print("🔄 Verwende Mock Services für Tests")
#             self.clu_service = None
#             self.speech_service = None
#
#         # Unterstützte Audio-Formate
#         self.supported_audio_types = {
#             'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp3', 'audio/x-wav', 'audio/wave'
#         }
#
#         # State Handler Mapping
#         self.state_handlers = {
#             SimplifiedAudioStates.START: self._handle_start,
#             SimplifiedAudioStates.ASK_NAME: self._handle_name_input,
#             SimplifiedAudioStates.ASK_BIRTHDATE: self._handle_birthdate_input,
#             SimplifiedAudioStates.ASK_EMAIL: self._handle_email_input,
#             SimplifiedAudioStates.ASK_PHONE: self._handle_phone_input,
#             SimplifiedAudioStates.ASK_ADDRESS: self._handle_address_input,
#             SimplifiedAudioStates.ASK_POSTAL_CITY: self._handle_postal_city_input,
#             SimplifiedAudioStates.ASK_COUNTRY: self._handle_country_input,
#             SimplifiedAudioStates.FINAL_VALIDATION: self._handle_final_validation,
#         }
#
#         print("✅ Vereinfachter Audio Bot initialisiert")
#
#     async def on_message_activity(self, turn_context: TurnContext):
#         """Verarbeitet eingehende Audio-Nachrichten."""
#         print("\n" + "=" * 50)
#         print("🎤 AUDIO MESSAGE - VEREINFACHTER FLOW")
#         print("=" * 50)
#
#         try:
#             attachments = turn_context.activity.attachments or []
#             audio_attachments = [att for att in attachments if att.content_type in self.supported_audio_types]
#
#             if not audio_attachments:
#                 await self._send_audio_only_message(turn_context)
#                 return
#
#             # Audio verarbeiten
#             attachment = audio_attachments[0]
#             await self._process_audio_message(turn_context, attachment)
#
#         except Exception as e:
#             print(f"❌ Fehler in on_message_activity: {e}")
#             await self._send_audio_response(turn_context,
#                                             "Entschuldigung, es gab einen Fehler beim Verarbeiten Ihrer Nachricht.")
#
#         # State speichern
#         await self.conversation_state.save_changes(turn_context)
#         await self.user_state.save_changes(turn_context)
#
#     async def _process_audio_message(self, turn_context: TurnContext, attachment: Attachment):
#         """Verarbeitet Audio-Nachricht gemäß Sprachfluss."""
#         try:
#             # 1. Audio herunterladen
#             audio_bytes = await self._download_audio(attachment)
#             if not audio_bytes:
#                 await self._send_audio_response(turn_context, "Ich konnte die Audio-Datei nicht laden.")
#                 return
#
#             # 2. Speech-to-Text
#             if self.speech_service:
#                 stt_result = self.speech_service.speech_to_text_from_bytes(audio_bytes)
#                 if not stt_result.get('success'):
#                     await self._send_audio_response(turn_context,
#                                                     "Entschuldigung, ich konnte Ihre Sprache nicht verstehen. Bitte sprechen Sie deutlicher.")
#                     return
#
#                 recognized_text = stt_result.get('text', '').strip()
#                 print(f"🗣️ Erkannter Text: '{recognized_text}'")
#             else:
#                 # Mock für Tests ohne Azure Speech Service
#                 print("🧪 Mock STT: Azure Speech Service nicht verfügbar")
#                 print(f"🧪 Audio Bytes erhalten: {len(audio_bytes)} bytes")
#
#                 # Simuliere verschiedene Test-Eingaben basierend auf aktueller Dialog-State
#                 dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: SimplifiedAudioStates.START)
#
#                 mock_responses = {
#                     SimplifiedAudioStates.START: "Hallo, ich möchte mich registrieren",
#                     SimplifiedAudioStates.ASK_NAME: "Max Mustermann",
#                     SimplifiedAudioStates.ASK_BIRTHDATE: "15.03.1990",
#                     SimplifiedAudioStates.ASK_EMAIL: "max.mustermann@example.com",
#                     SimplifiedAudioStates.ASK_PHONE: "0123456789",
#                     SimplifiedAudioStates.ASK_ADDRESS: "Musterstraße 123",
#                     SimplifiedAudioStates.ASK_POSTAL_CITY: "12345 Berlin",
#                     SimplifiedAudioStates.ASK_COUNTRY: "Deutschland",
#                     SimplifiedAudioStates.FINAL_VALIDATION: "ja"
#                 }
#
#                 recognized_text = mock_responses.get(dialog_state, "Test-Eingabe")
#                 print(f"🧪 Mock erkannter Text für State '{dialog_state}': '{recognized_text}'")
#
#             if not recognized_text:
#                 await self._send_audio_response(turn_context,
#                                                 "Ich habe nichts verstanden. Bitte sprechen Sie lauter.")
#                 return
#
#             # 3. CLU Analyse (für besseres Verständnis)
#             try:
#                 clu_result = await self.clu_service.analyze_conversation(recognized_text)
#                 print(f"🧠 CLU: {clu_result.get('total_intents_found', 0)} Intents gefunden")
#             except Exception as e:
#                 print(f"⚠️ CLU Fehler: {e}")
#
#             # 4. Dialog-State basierte Verarbeitung
#             user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
#             dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: SimplifiedAudioStates.START)
#
#             # State Handler aufrufen
#             if dialog_state in self.state_handlers:
#                 await self.state_handlers[dialog_state](turn_context, user_profile, recognized_text)
#             else:
#                 await self._handle_start(turn_context, user_profile, recognized_text)
#
#         except Exception as e:
#             print(f"❌ Fehler in _process_audio_message: {e}")
#             await self._send_audio_response(turn_context, "Bei der Verarbeitung ist ein Fehler aufgetreten.")
#
#     # === STATE HANDLERS (Sprachfluss) ===
#
#     async def _handle_start(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Start der Konversation - Begrüßung & Erklärung des Ziels"""
#         welcome_text = (
#             "Hallo! Willkommen bei unserem Sprach-Registrierungsbot. "
#             "Ich helfe Ihnen dabei, ein neues Kundenkonto zu erstellen. "
#             "Dafür benötige ich einige persönliche Informationen von Ihnen. "
#             "Lassen Sie uns mit Ihrem Namen beginnen."
#         )
#         await self._send_audio_response(turn_context, welcome_text)
#         await self._ask_for_name(turn_context)
#
#     async def _ask_for_name(self, turn_context: TurnContext):
#         """Frage nach Vor- und Nachname"""
#         await self._send_audio_response(turn_context,
#                                         "Bitte sagen Sie mir Ihren vollständigen Namen, also Vor- und Nachname.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_NAME)
#
#     async def _handle_name_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung der Namenseingabe"""
#         # Einfache Namensextraktion (Vor- und Nachname)
#         name_parts = user_input.strip().split()
#
#         if len(name_parts) >= 2:
#             first_name = name_parts[0]
#             last_name = " ".join(name_parts[1:])
#
#             if self._validate_name_part(first_name) and self._validate_name_part(last_name):
#                 user_profile['first_name'] = first_name
#                 user_profile['last_name'] = last_name
#                 await self.user_profile_accessor.set(turn_context, user_profile)
#
#                 # Bestätigung
#                 confirmation = f"Ich habe verstanden: {first_name} {last_name}. Ist das korrekt?"
#                 await self._send_audio_response(turn_context, confirmation)
#
#                 # Warte auf Bestätigung oder gehe weiter
#                 await self._ask_for_birthdate(turn_context)
#             else:
#                 await self._send_audio_response(turn_context,
#                                                 "Der Name wurde nicht korrekt verstanden. Bitte sagen Sie Ihren vollständigen Namen noch einmal deutlich.")
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Bitte sagen Sie sowohl Ihren Vor- als auch Nachnamen.")
#
#     async def _ask_for_birthdate(self, turn_context: TurnContext):
#         """Frage nach Geburtsdatum"""
#         await self._send_audio_response(turn_context,
#                                         "Nun benötige ich Ihr Geburtsdatum. Bitte sagen Sie es im Format Tag, Monat, Jahr. "
#                                         "Zum Beispiel: fünfzehnter März neunzehnhundert neunzig.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_BIRTHDATE)
#
#     async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung der Geburtsdatumseingabe"""
#         birthdate = self._extract_birthdate_from_text(user_input)
#
#         if birthdate:
#             user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
#             user_profile['birth_date_display'] = birthdate.strftime('%d.%m.%Y')
#             await self.user_profile_accessor.set(turn_context, user_profile)
#
#             confirmation = f"Ihr Geburtsdatum ist der {birthdate.strftime('%d.%m.%Y')}. Ist das richtig?"
#             await self._send_audio_response(turn_context, confirmation)
#             await self._ask_for_email(turn_context)
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Das Geburtsdatum wurde nicht korrekt verstanden. Bitte sagen Sie es noch einmal, "
#                                             "zum Beispiel: fünfter Mai neunzehnhundert achtzig.")
#
#     async def _ask_for_email(self, turn_context: TurnContext):
#         """Frage nach E-Mail-Adresse"""
#         await self._send_audio_response(turn_context,
#                                         "Jetzt benötige ich Ihre E-Mail-Adresse. Bitte buchstabieren Sie sie deutlich.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_EMAIL)
#
#     async def _handle_email_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung der E-Mail-Eingabe"""
#         email = self._extract_email_from_text(user_input)
#
#         if email and self._validate_email(email):
#             if await self._email_exists_in_db(email):
#                 await self._send_audio_response(turn_context,
#                                                 "Diese E-Mail-Adresse ist bereits registriert. Bitte geben Sie eine andere E-Mail-Adresse an.")
#                 return
#
#             user_profile['email'] = email
#             await self.user_profile_accessor.set(turn_context, user_profile)
#
#             confirmation = f"Ihre E-Mail-Adresse ist {email}. Ist das korrekt?"
#             await self._send_audio_response(turn_context, confirmation)
#             await self._ask_for_phone(turn_context)
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Die E-Mail-Adresse wurde nicht korrekt verstanden. Bitte buchstabieren Sie sie noch einmal deutlich.")
#
#     async def _ask_for_phone(self, turn_context: TurnContext):
#         """Frage nach Telefonnummer"""
#         await self._send_audio_response(turn_context,
#                                         "Nun benötige ich Ihre Telefonnummer. Bitte sagen Sie die Ziffern einzeln und deutlich.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_PHONE)
#
#     async def _handle_phone_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung der Telefonnummereingabe"""
#         phone = self._extract_phone_from_text(user_input)
#
#         if phone and self._validate_phone(phone):
#             user_profile['telephone'] = phone
#             user_profile['telephone_display'] = user_input
#             await self.user_profile_accessor.set(turn_context, user_profile)
#
#             confirmation = f"Ihre Telefonnummer ist {phone}. Ist das richtig?"
#             await self._send_audio_response(turn_context, confirmation)
#             await self._ask_for_address(turn_context)
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Die Telefonnummer wurde nicht korrekt verstanden. Bitte sagen Sie die Ziffern noch einmal einzeln.")
#
#     async def _ask_for_address(self, turn_context: TurnContext):
#         """Frage nach Straße und Hausnummer"""
#         await self._send_audio_response(turn_context,
#                                         "Jetzt benötige ich Ihre Adresse. Bitte sagen Sie mir Straße und Hausnummer.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_ADDRESS)
#
#     async def _handle_address_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung der Adresseingabe"""
#         street, house_number = self._extract_street_and_number(user_input)
#
#         if street and house_number:
#             user_profile['street_name'] = street
#             user_profile['house_number'] = house_number
#             user_profile['house_number_addition'] = ""
#             await self.user_profile_accessor.set(turn_context, user_profile)
#
#             confirmation = f"Ihre Adresse ist {street} {house_number}. Ist das korrekt?"
#             await self._send_audio_response(turn_context, confirmation)
#             await self._ask_for_postal_city(turn_context)
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Die Adresse wurde nicht korrekt verstanden. Bitte sagen Sie Straße und Hausnummer noch einmal.")
#
#     async def _ask_for_postal_city(self, turn_context: TurnContext):
#         """Frage nach PLZ und Ort"""
#         await self._send_audio_response(turn_context,
#                                         "Nun benötige ich Ihre Postleitzahl und Ihren Wohnort.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_POSTAL_CITY)
#
#     async def _handle_postal_city_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung von PLZ und Ort"""
#         postal_code, city = self._extract_postal_and_city(user_input)
#
#         if postal_code and city:
#             user_profile['postal_code'] = postal_code
#             user_profile['city'] = city
#             await self.user_profile_accessor.set(turn_context, user_profile)
#
#             confirmation = f"Postleitzahl {postal_code}, Ort {city}. Ist das richtig?"
#             await self._send_audio_response(turn_context, confirmation)
#             await self._ask_for_country(turn_context)
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Postleitzahl und Ort wurden nicht korrekt verstanden. Bitte wiederholen Sie beides.")
#
#     async def _ask_for_country(self, turn_context: TurnContext):
#         """Frage nach Land"""
#         await self._send_audio_response(turn_context,
#                                         "Abschließend benötige ich noch Ihr Land.")
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_COUNTRY)
#
#     async def _handle_country_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Verarbeitung der Ländereingabe"""
#         country = user_input.strip().title()
#
#         if len(country) >= 2:
#             user_profile['country_name'] = country
#             await self.user_profile_accessor.set(turn_context, user_profile)
#
#             confirmation = f"Ihr Land ist {country}. Ist das korrekt?"
#             await self._send_audio_response(turn_context, confirmation)
#             await self._final_validation(turn_context)
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Das Land wurde nicht korrekt verstanden. Bitte sagen Sie es noch einmal.")
#
#     async def _final_validation(self, turn_context: TurnContext):
#         """Finale Validierung aller Daten"""
#         user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
#
#         # Alle Daten zusammenfassen
#         summary = (
#             f"Vielen Dank! Hier ist eine Zusammenfassung Ihrer Angaben: "
#             f"Name: {user_profile.get('first_name')} {user_profile.get('last_name')}, "
#             f"Geburtsdatum: {user_profile.get('birth_date_display')}, "
#             f"E-Mail: {user_profile.get('email')}, "
#             f"Telefon: {user_profile.get('telephone')}, "
#             f"Adresse: {user_profile.get('street_name')} {user_profile.get('house_number')}, "
#             f"Postleitzahl und Ort: {user_profile.get('postal_code')} {user_profile.get('city')}, "
#             f"Land: {user_profile.get('country_name')}. "
#             f"Sind alle Angaben korrekt und soll ich Ihr Konto erstellen?"
#         )
#
#         await self._send_audio_response(turn_context, summary)
#         await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.FINAL_VALIDATION)
#
#     async def _handle_final_validation(self, turn_context: TurnContext, user_profile: dict, user_input: str):
#         """Behandlung der finalen Bestätigung"""
#         user_input_lower = user_input.lower()
#
#         if any(word in user_input_lower for word in ["ja", "yes", "richtig", "korrekt", "okay", "ok"]):
#             # Daten speichern
#             success = await self._save_customer_data(user_profile)
#
#             if success:
#                 await self._send_audio_response(turn_context,
#                                                 "Perfekt! Ihre Daten wurden erfolgreich gespeichert und Ihr Konto wurde erstellt. "
#                                                 "Vielen Dank für Ihre Registrierung!")
#                 await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.COMPLETED)
#             else:
#                 await self._send_audio_response(turn_context,
#                                                 "Entschuldigung, beim Speichern ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.")
#
#         elif any(word in user_input_lower for word in ["nein", "no", "falsch", "inkorrekt"]):
#             await self._send_audio_response(turn_context,
#                                             "Verstanden. Die Registrierung wurde abgebrochen. Sie können jederzeit neu starten.")
#             await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.START)
#             await self.user_profile_accessor.set(turn_context, {})
#
#         else:
#             await self._send_audio_response(turn_context,
#                                             "Bitte antworten Sie mit ja oder nein.")
#
#     # === HILFSMETHODEN ===
#
#     async def _download_audio(self, attachment: Attachment) -> bytes:
#         """Lädt Audio-Attachment herunter"""
#         try:
#             async with aiohttp.ClientSession() as session:
#                 async with session.get(attachment.content_url) as response:
#                     if response.status == 200:
#                         return await response.read()
#             return None
#         except Exception as e:
#             print(f"❌ Download Error: {e}")
#             return None
#
#     async def _send_audio_response(self, turn_context: TurnContext, text: str):
#         """Sendet Antwort als Audio"""
#         try:
#             print(f"🔊 Generiere Audio für: '{text}'")
#
#             # Text-to-Speech (falls verfügbar)
#             if self.speech_service:
#                 audio_bytes = self.speech_service.text_to_speech_bytes(text)
#
#                 if audio_bytes:
#                     import base64
#                     audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
#
#                     attachment = Attachment(
#                         content_type="audio/wav",
#                         content_url=f"data:audio/wav;base64,{audio_base64}",
#                         name="bot_response.wav"
#                     )
#
#                     reply = MessageFactory.attachment(attachment)
#                     reply.text = f"🔊 {text}"
#                     await turn_context.send_activity(reply)
#                     return
#
#             # Fallback: Text-Nachricht (für Docker/Mock-Modus)
#             print("🔊 Sende Text-Fallback (kein TTS verfügbar)")
#             await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))
#
#         except Exception as e:
#             print(f"❌ Audio Response Error: {e}")
#             # Letzter Fallback: einfache Text-Nachricht
#             try:
#                 await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))
#             except Exception as e2:
#                 print(f"❌ Auch Text-Fallback fehlgeschlagen: {e2}")
#
#     async def _send_audio_only_message(self, turn_context: TurnContext):
#         """Hinweis für Nur-Audio-Modus"""
#         await self._send_audio_response(turn_context,
#                                         "Hallo! Ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht für die Registrierung.")
#
#     # === VALIDIERUNGS- UND EXTRAKTIONSMETHODEN ===
#
#     def _validate_name_part(self, name: str) -> bool:
#         """Validiert Namensteil"""
#         return len(name.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\']+$', name.strip())
#
#     def _extract_birthdate_from_text(self, text: str) -> Optional[datetime]:
#         """Extrahiert Geburtsdatum aus gesprochenem Text"""
#         try:
#             # Vereinfachte Extraktion - sollte erweitert werden
#             import re
#             date_patterns = [
#                 r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
#                 r'(\d{1,2}) (\d{1,2}) (\d{4})',
#             ]
#
#             for pattern in date_patterns:
#                 match = re.search(pattern, text)
#                 if match:
#                     day, month, year = map(int, match.groups())
#                     return datetime(year, month, day)
#
#             return None
#         except:
#             return None
#
#     def _extract_email_from_text(self, text: str) -> Optional[str]:
#         """Extrahiert E-Mail aus gesprochenem Text"""
#         import re
#         # Einfache E-Mail-Extraktion
#         email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
#         match = re.search(email_pattern, text)
#         return match.group() if match else None
#
#     def _extract_phone_from_text(self, text: str) -> Optional[str]:
#         """Extrahiert Telefonnummer aus gesprochenem Text"""
#         import re
#         # Entferne Leerzeichen und extrahiere Ziffern
#         digits = re.sub(r'[^\d+]', '', text)
#         return digits if len(digits) >= 10 else None
#
#     def _extract_street_and_number(self, text: str) -> tuple:
#         """Extrahiert Straße und Hausnummer"""
#         import re
#         # Vereinfachte Extraktion
#         match = re.search(r'(.+?)\s+(\d+[a-zA-Z]?)$', text.strip())
#         if match:
#             return match.group(1).strip(), match.group(2)
#         return None, None
#
#     def _extract_postal_and_city(self, text: str) -> tuple:
#         """Extrahiert PLZ und Stadt"""
#         import re
#         match = re.search(r'(\d{5})\s+(.+)', text.strip())
#         if match:
#             return match.group(1), match.group(2).strip()
#         return None, None
#
#     def _validate_email(self, email: str) -> bool:
#         """Validiert E-Mail"""
#         try:
#             validate_email(email)
#             return True
#         except ValidationError:
#             return False
#
#     def _validate_phone(self, phone: str) -> bool:
#         """Validiert Telefonnummer"""
#         try:
#             parsed = parse(phone, "DE")
#             return is_valid_number(parsed)
#         except NumberParseException:
#             return False
#
#     async def _email_exists_in_db(self, email: str) -> bool:
#         """Prüft E-Mail in DB"""
#         return await sync_to_async(CustomerContact.objects.filter(email=email).exists)()
#
#     async def _save_customer_data(self, user_profile: dict) -> bool:
#         """Speichert Kundendaten in DB"""
#         try:
#             # Vereinfachte Speicherung - nutze die Logik vom ursprünglichen Bot
#             async def _get_or_create(model, **kwargs):
#                 return await sync_to_async(model.objects.get_or_create)(**kwargs)
#
#             async def _create(model, **kwargs):
#                 return await sync_to_async(model.objects.create)(**kwargs)
#
#             # Country
#             country_obj, _ = await _get_or_create(
#                 AddressCountry, country_name=user_profile['country_name']
#             )
#
#             # Street
#             street_obj, _ = await _get_or_create(
#                 AddressStreet, street_name=user_profile['street_name']
#             )
#
#             # City
#             city_obj, _ = await _get_or_create(
#                 AddressCity,
#                 city=user_profile['city'],
#                 postal_code=user_profile['postal_code'],
#                 country=country_obj
#             )
#
#             # Address
#             address_obj = await _create(
#                 Address,
#                 street=street_obj,
#                 house_number=int(user_profile['house_number']),
#                 house_number_addition=user_profile.get('house_number_addition', ''),
#                 place=city_obj
#             )
#
#             # Customer
#             birth_date = datetime.strptime(user_profile['birth_date'], "%Y-%m-%d").date()
#             customer = await _create(
#                 Customer,
#                 gender='unspecified',  # Vereinfacht
#                 first_name=user_profile['first_name'],
#                 second_name=user_profile['last_name'],
#                 birth_date=birth_date,
#                 title='',
#                 address=address_obj
#             )
#
#             # Contact
#             from phonenumber_field.phonenumber import PhoneNumber
#             phone_obj = PhoneNumber.from_string(user_profile['telephone'], region="DE")
#
#             await _create(
#                 CustomerContact,
#                 customer=customer,
#                 email=user_profile['email'],
#                 telephone=phone_obj
#             )
#
#             print(f"✅ Customer {customer.customer_id} erfolgreich gespeichert!")
#             return True
#
#         except Exception as e:
#             print(f"❌ Speicherfehler: {e}")
#             import traceback
#             traceback.print_exc()
#             return False
#
#     async def on_members_added_activity(self, members_added, turn_context: TurnContext):
#         """Begrüßung für neue Mitglieder"""
#         for member in members_added:
#             if member.id != turn_context.activity.recipient.id:
#                 await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.START)
#                 await self._handle_start(turn_context, {}, "")
#                 break
#
#         await self.conversation_state.save_changes(turn_context)
#         await self.user_state.save_changes(turn_context)
#

import aiohttp
import base64
import re
from datetime import datetime
from injector import inject

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount, Attachment

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
        super().__init__()
        print("🎤 Initialisiere Audio Registration Bot...")

        # Core Services (identisch zum Text-Bot)
        self.customer_service = customer_service
        self.conversation_state = conversation_state
        self.user_state = user_state

        # State Accessors (identisch zum Text-Bot)
        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")

        if isDocker:
            print("⚠️ KeyVault Service nicht verfügbar")
            self.clu_service = None
            self.speech_service = None
        else:
            #self.clu_service = AzureCLUService()
            self.speech_service = AzureSpeechService()

            test_audio = self.speech_service.text_to_speech_bytes("Test")

            if test_audio and len(test_audio) > 0:
                print(f"✅ Speech Service funktioniert! TTS Test: {len(test_audio)} bytes")

            print("✅ Azure Services erfolgreich initialisiert")

        self.supported_audio_types = {
            'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp3', 'audio/x-wav', 'audio/wave'
        }

        # Dialog Handlers (identische Struktur wie Text-Bot)
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

    def _initialize_speech_service(self):
        """Initialisiert Azure Speech Service - OHNE Mock-Fallback"""
        try:
            print("🎵 Initialisiere Azure Speech Service...")
            speech_service = AzureSpeechService()

            # TTS Test
            print("🎵 Teste TTS...")
            test_audio = speech_service.text_to_speech_bytes("Test")

            if test_audio and len(test_audio) > 0:
                print(f"✅ Speech Service funktioniert! TTS Test: {len(test_audio)} bytes")
                return speech_service
            else:
                print("❌ TTS Test fehlgeschlagen")
                raise Exception("TTS Test fehlgeschlagen")

        except Exception as e:
            print(f"❌ Speech Service Fehler: {e}")
            print("❌ KRITISCHER FEHLER: Audio Bot kann nicht ohne Speech Service funktionieren!")
            raise Exception(f"Speech Service erforderlich: {e}")

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
            # 1. Input-Typ validieren und extrahieren
            user_input = await self._extract_and_validate_input(turn_context)
            if user_input is None:  # Fehler beim Input oder ungültiger Typ
                return

            # 2. User Profile und Dialog State abrufen (identisch zum Text-Bot)
            user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
            dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

            print(f"🎯 Current State: {dialog_state}")
            print(f"🗣️ User Input: '{user_input}'")

            # 3. Auto-start für neue User (identisch zum Text-Bot)
            if not user_profile and dialog_state == DialogState.GREETING:
                user_profile['first_interaction'] = True
                await self.user_profile_accessor.set(turn_context, user_profile)
                await self._handle_greeting(turn_context, user_profile)
                await self._save_state(turn_context)
                return

            # 4. Dialog-Routing (identische Logik wie Text-Bot)
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

            # 5. State speichern (identisch zum Text-Bot)
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

    async def _download_audio(self, attachment: Attachment) -> bytes:
        """Lädt Audio herunter"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.content_url) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception as e:
            print(f"❌ Download Fehler: {e}")
        return None

    # === INPUT VALIDATION UND EXTRAKTION ===

    async def _extract_and_validate_input(self, turn_context: TurnContext) -> str:
        """
        Validiert Input-Typ und extrahiert Text.
        Bei Text-Input: Fehler ausgeben, aber State beibehalten.
        Bei Audio-Input: STT durchführen.
        """
        attachments = turn_context.activity.attachments or []
        audio_attachments = [att for att in attachments if att.content_type in self.supported_audio_types]
        text_input = turn_context.activity.text

        # Fall 1: Text-Input erkannt
        if text_input and text_input.strip() and not audio_attachments:
            print(f"❌ Text-Input erkannt: '{text_input}'")
            await self._send_audio_response(turn_context,
                                            "Entschuldigung, ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht.")
            return None

        # Fall 2: Kein Audio-Input
        if not audio_attachments:
            print("❌ Kein Audio-Input erkannt")
            await self._send_audio_response(turn_context,
                                            "Hallo! Ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht.")
            return None

        # Fall 3: Audio-Input verarbeiten
        return await self._process_audio_input(turn_context, audio_attachments[0])

    async def _process_audio_input(self, turn_context: TurnContext, attachment: Attachment) -> str:
        """Verarbeitet Audio-Input OHNE Mock-Fallback"""
        try:
            # Audio herunterladen
            print("📥 Lade Audio herunter...")
            audio_bytes = await self._download_audio(attachment)
            if not audio_bytes:
                await self._send_audio_response(turn_context, "Audio konnte nicht geladen werden.")
                return None

            print(f"📥 Audio geladen: {len(audio_bytes)} bytes")

            # Speech-to-Text (OHNE Mock-Fallback)
            if not self.speech_service:
                print("❌ KRITISCHER FEHLER: Kein Speech Service verfügbar")
                await self._send_audio_response(turn_context,
                                                "Entschuldigung, der Sprach-Service ist nicht verfügbar. Bitte versuchen Sie es später erneut.")
                return None

            print("🎤 Starte STT...")
            stt_result = self.speech_service.speech_to_text_from_bytes(audio_bytes)
            print(f"🎤 STT Result: {stt_result}")

            if stt_result.get('success'):
                recognized_text = stt_result.get('text', '').strip()
                print(f"🗣️ STT Erkannt: '{recognized_text}'")

                # NEU: Text auch als Nachricht ausgeben
                await self._send_recognized_text_display(turn_context, recognized_text)

                return recognized_text
            else:
                error_msg = stt_result.get('error', 'Unbekannter STT-Fehler')
                print(f"❌ STT Fehler: {error_msg}")
                await self._send_audio_response(turn_context,
                                                "Ich konnte Sie nicht verstehen. Bitte sprechen Sie deutlicher.")
                return None

        except Exception as e:
            print(f"❌ Fehler bei Audio-Verarbeitung: {e}")
            await self._send_audio_response(turn_context, "Fehler beim Verarbeiten der Sprache.")
            return None

    async def _send_audio_response(self, turn_context: TurnContext, text: str):
        """
        Sendet Audio-Antwort mit TTS.
        Bei TTS-Fehler: Fallback zu Text (aber mit Audio-Icon).
        """
        try:
            print(f"🔊 Generiere Audio für: '{text[:50]}{'...' if len(text) > 50 else ''}'")

            if self.speech_service:
                print("🎵 Starte TTS...")
                audio_bytes = self.speech_service.text_to_speech_bytes(text)

                if audio_bytes and len(audio_bytes) > 0:
                    print(f"✅ TTS Audio generiert: {len(audio_bytes)} bytes")

                    # Base64 kodieren
                    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    print(f"✅ Base64 kodiert: {len(audio_base64)} Zeichen")

                    # Audio-Attachment erstellen
                    attachment = Attachment(
                        content_type="audio/wav",
                        content_url=f"data:audio/wav;base64,{audio_base64}",
                        name="bot_response.wav"
                    )

                    # Nachricht mit Audio senden
                    reply = MessageFactory.attachment(attachment)
                    reply.text = f"🔊 {text}"  # Text als Fallback
                    await turn_context.send_activity(reply)
                    print("✅ Audio-Nachricht gesendet")
                    return
                else:
                    print("❌ TTS generierte kein Audio")

            # Fallback: Text mit Audio-Symbol
            print("🔊 Fallback: Sende Text mit Audio-Symbol")
            await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))

        except Exception as e:
            print(f"❌ TTS Fehler: {e}")
            # Letzter Fallback: Reiner Text
            await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))

    # === TEXT-TO-SPEECH HILFSMETHODEN ===

    def _convert_markdown_to_speech(self, text: str) -> str:
        """Konvertiert Markdown zu sprachfreundlichem Text"""
        speech_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** -> bold
        speech_text = re.sub(r'\*([^*]+)\*', r'\1', speech_text)  # *italic* -> italic
        speech_text = re.sub(r'•\s*', '', speech_text)  # Bullet points entfernen
        speech_text = re.sub(r'\n+', ' ', speech_text)  # Zeilenumbrüche zu Leerzeichen
        speech_text = re.sub(r'\s+', ' ', speech_text)  # Mehrfache Leerzeichen entfernen
        return speech_text.strip()

    def _get_mock_input(self, state: str) -> str:
        """Mock-Eingaben für Tests ohne Speech Service"""
        mock_responses = {
            DialogState.GREETING: "ja",
            DialogState.ASK_CONSENT: "ja",
            DialogState.ASK_GENDER: "männlich",
            DialogState.ASK_TITLE: "kein",
            DialogState.ASK_FIRST_NAME: "Max",
            DialogState.ASK_LAST_NAME: "Mustermann",
            DialogState.ASK_BIRTHDATE: "15.03.1990",
            DialogState.ASK_EMAIL: "max.mustermann@example.com",
            DialogState.ASK_PHONE: "0123456789",
            DialogState.ASK_STREET: "Musterstraße",
            DialogState.ASK_HOUSE_NUMBER: "123",
            DialogState.ASK_HOUSE_ADDITION: "kein",
            DialogState.ASK_POSTAL: "12345",
            DialogState.ASK_CITY: "Berlin",
            DialogState.ASK_COUNTRY: "Deutschland",
            DialogState.FINAL_CONFIRMATION: "ja"
        }
        return mock_responses.get(state, "ja")

    async def _send_recognized_text_display(self, turn_context: TurnContext, recognized_text: str):
        """
        Sendet den erkannten Text als separate Nachricht zur Anzeige.
        Zeigt dem User, was der Bot verstanden hat.
        """
        try:
            display_message = f"📝 Verstanden: \"{recognized_text}\""
            print(f"📝 Sende erkannten Text: {display_message}")

            # Als normale Text-Nachricht senden (ohne Audio)
            await turn_context.send_activity(MessageFactory.text(display_message))

        except Exception as e:
            print(f"❌ Fehler beim Senden des erkannten Texts: {e}")
            # Nicht kritisch - nur Logging

    async def _send_audio_response(self, turn_context: TurnContext, text: str):
        """
        Sendet Audio-Antwort mit TTS - OHNE Mock-Fallback.
        Zeigt auch den Text an, der zu Audio konvertiert wird.
        """
        try:
            print(f"🔊 Generiere Audio für: '{text[:100]}{'...' if len(text) > 100 else ''}'")

            # NEU: Text-Anzeige vor Audio-Generierung
            await self._send_bot_text_display(turn_context, text)

            if not self.speech_service:
                print("❌ KRITISCHER FEHLER: Kein Speech Service für TTS verfügbar")
                # Nur Text senden, da kein Audio möglich
                await turn_context.send_activity(MessageFactory.text(f"❌ [Audio nicht verfügbar] {text}"))
                return

            print("🎵 Starte TTS...")
            audio_bytes = self.speech_service.text_to_speech_bytes(text)

            if audio_bytes and len(audio_bytes) > 0:
                print(f"✅ TTS Audio generiert: {len(audio_bytes)} bytes")

                # Base64 kodieren
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                print(f"✅ Base64 kodiert: {len(audio_base64)} Zeichen")

                # Audio-Attachment erstellen
                attachment = Attachment(
                    content_type="audio/wav",
                    content_url=f"data:audio/wav;base64,{audio_base64}",
                    name="bot_response.wav"
                )

                # Nachricht mit Audio senden
                reply = MessageFactory.attachment(attachment)
                reply.text = f"🔊 Audio-Antwort"  # Kurzer Text als Fallback
                await turn_context.send_activity(reply)
                print("✅ Audio-Nachricht gesendet")
            else:
                print("❌ TTS generierte kein Audio")
                await turn_context.send_activity(MessageFactory.text(f"❌ [TTS fehlgeschlagen] {text}"))

        except Exception as e:
            print(f"❌ TTS Fehler: {e}")
            # Kritischer Fallback: Text ohne Audio
            await turn_context.send_activity(MessageFactory.text(f"❌ [Audio-Fehler] {text}"))

    # === NEUE METHODE: BOT TEXT ANZEIGEN ===

    async def _send_bot_text_display(self, turn_context: TurnContext, text: str):
        """
        Sendet den Bot-Text als separate Nachricht zur Anzeige.
        Zeigt dem User, was der Bot sagen wird (bevor das Audio kommt).
        """
        try:
            # Text für bessere Lesbarkeit vorbereiten
            display_text = self._convert_markdown_to_speech(text)
            display_message = f"🤖 Bot: {display_text}"
            print(f"🤖 Sende Bot-Text: {display_message[:100]}{'...' if len(display_message) > 100 else ''}")

            # Als normale Text-Nachricht senden
            await turn_context.send_activity(MessageFactory.text(display_message))

        except Exception as e:
            print(f"❌ Fehler beim Senden des Bot-Texts: {e}")
            # Nicht kritisch - nur Logging

    async def _extract_and_validate_input(self, turn_context: TurnContext) -> str:
        """
        Validiert Input-Typ und extrahiert Text - OHNE Mock-Fallback.
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

        # Fall 3: Audio-Input verarbeiten (OHNE Mock)
        return await self._process_audio_input(turn_context, audio_attachments[0])

    # === PLACEHOLDER DIALOG HANDLERS (Grundgerüst) ===

    async def _handle_greeting(self, turn_context: TurnContext, user_profile, *args):
        """Placeholder für Begrüßung"""
        print("🎯 Handler: Greeting")
        greeting_text = self._convert_markdown_to_speech(BotMessages.WELCOME_MESSAGE)
        await self._send_audio_response(turn_context, greeting_text)
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CONSENT)

    async def _handle_consent_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Consent"""
        print(f"🎯 Handler: Consent Input - '{user_input}'")
        # TODO: Implement consent logic
        await self._send_audio_response(turn_context, "Consent Handler - Placeholder")

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Gender"""
        print(f"🎯 Handler: Gender Input - '{user_input}'")
        # TODO: Implement gender logic
        await self._send_audio_response(turn_context, "Gender Handler - Placeholder")

    async def _handle_title_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Title"""
        print(f"🎯 Handler: Title Input - '{user_input}'")
        # TODO: Implement title logic
        await self._send_audio_response(turn_context, "Title Handler - Placeholder")

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für First Name"""
        print(f"🎯 Handler: First Name Input - '{user_input}'")
        # TODO: Implement first name logic
        await self._send_audio_response(turn_context, "First Name Handler - Placeholder")

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Last Name"""
        print(f"🎯 Handler: Last Name Input - '{user_input}'")
        # TODO: Implement last name logic
        await self._send_audio_response(turn_context, "Last Name Handler - Placeholder")

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Birthdate"""
        print(f"🎯 Handler: Birthdate Input - '{user_input}'")
        # TODO: Implement birthdate logic
        await self._send_audio_response(turn_context, "Birthdate Handler - Placeholder")

    async def _handle_email_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Email"""
        print(f"🎯 Handler: Email Input - '{user_input}'")
        # TODO: Implement email logic
        await self._send_audio_response(turn_context, "Email Handler - Placeholder")

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Phone"""
        print(f"🎯 Handler: Phone Input - '{user_input}'")
        # TODO: Implement phone logic
        await self._send_audio_response(turn_context, "Phone Handler - Placeholder")

    async def _handle_street_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Street"""
        print(f"🎯 Handler: Street Input - '{user_input}'")
        # TODO: Implement street logic
        await self._send_audio_response(turn_context, "Street Handler - Placeholder")

    async def _handle_house_number_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für House Number"""
        print(f"🎯 Handler: House Number Input - '{user_input}'")
        # TODO: Implement house number logic
        await self._send_audio_response(turn_context, "House Number Handler - Placeholder")

    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für House Addition"""
        print(f"🎯 Handler: House Addition Input - '{user_input}'")
        # TODO: Implement house addition logic
        await self._send_audio_response(turn_context, "House Addition Handler - Placeholder")

    async def _handle_postal_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Postal"""
        print(f"🎯 Handler: Postal Input - '{user_input}'")
        # TODO: Implement postal logic
        await self._send_audio_response(turn_context, "Postal Handler - Placeholder")

    async def _handle_city_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für City"""
        print(f"🎯 Handler: City Input - '{user_input}'")
        # TODO: Implement city logic
        await self._send_audio_response(turn_context, "City Handler - Placeholder")

    async def _handle_country_input(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Country"""
        print(f"🎯 Handler: Country Input - '{user_input}'")
        # TODO: Implement country logic
        await self._send_audio_response(turn_context, "Country Handler - Placeholder")

    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Final Confirmation"""
        print(f"🎯 Handler: Final Confirmation - '{user_input}'")
        # TODO: Implement final confirmation logic
        await self._send_audio_response(turn_context, "Final Confirmation Handler - Placeholder")

    async def _handle_correction_selection(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Correction Selection"""
        print(f"🎯 Handler: Correction Selection - '{user_input}'")
        # TODO: Implement correction logic
        await self._send_audio_response(turn_context, "Correction Handler - Placeholder")

    async def _handle_confirmation(self, turn_context: TurnContext, user_profile, user_input, dialog_state):
        """Placeholder für Confirmation"""
        print(f"🎯 Handler: Confirmation - State: {dialog_state}, Input: '{user_input}'")
        # TODO: Implement confirmation logic
        await self._send_audio_response(turn_context, "Confirmation Handler - Placeholder")

    async def _handle_completed_state(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Completed State"""
        print(f"🎯 Handler: Completed State - '{user_input}'")
        # TODO: Implement completed state logic
        await self._send_audio_response(turn_context, "Completed State Handler - Placeholder")

    async def _handle_unknown_state(self, turn_context: TurnContext, user_profile, user_input):
        """Placeholder für Unknown State"""
        print(f"🎯 Handler: Unknown State - '{user_input}'")
        # TODO: Implement unknown state logic
        await self._send_audio_response(turn_context, "Unknown State Handler - Placeholder")

    async def _show_final_summary(self, turn_context: TurnContext):
        """Placeholder für Final Summary"""
        print("🎯 Handler: Show Final Summary")
        # TODO: Implement final summary logic
        await self._send_audio_response(turn_context, "Final Summary Handler - Placeholder")

    # === PLACEHOLDER ASK METHODS ===

    async def _ask_for_title(self, turn_context: TurnContext):
        print("🎯 Ask: Title")
        await self._send_audio_response(turn_context, "Ask Title - Placeholder")

    async def _ask_for_first_name(self, turn_context: TurnContext):
        print("🎯 Ask: First Name")
        await self._send_audio_response(turn_context, "Ask First Name - Placeholder")

    async def _ask_for_last_name(self, turn_context: TurnContext):
        print("🎯 Ask: Last Name")
        await self._send_audio_response(turn_context, "Ask Last Name - Placeholder")

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        print("🎯 Ask: Birthdate")
        await self._send_audio_response(turn_context, "Ask Birthdate - Placeholder")

    async def _ask_for_email(self, turn_context: TurnContext):
        print("🎯 Ask: Email")
        await self._send_audio_response(turn_context, "Ask Email - Placeholder")

    async def _ask_for_phone(self, turn_context: TurnContext):
        print("🎯 Ask: Phone")
        await self._send_audio_response(turn_context, "Ask Phone - Placeholder")

    async def _ask_for_street(self, turn_context: TurnContext):
        print("🎯 Ask: Street")
        await self._send_audio_response(turn_context, "Ask Street - Placeholder")

    async def _ask_for_house_number(self, turn_context: TurnContext):
        print("🎯 Ask: House Number")
        await self._send_audio_response(turn_context, "Ask House Number - Placeholder")

    async def _ask_for_house_addition(self, turn_context: TurnContext):
        print("🎯 Ask: House Addition")
        await self._send_audio_response(turn_context, "Ask House Addition - Placeholder")

    async def _ask_for_postal(self, turn_context: TurnContext):
        print("🎯 Ask: Postal")
        await self._send_audio_response(turn_context, "Ask Postal - Placeholder")

    async def _ask_for_city(self, turn_context: TurnContext):
        print("🎯 Ask: City")
        await self._send_audio_response(turn_context, "Ask City - Placeholder")

    async def _ask_for_country(self, turn_context: TurnContext):
        print("🎯 Ask: Country")
        await self._send_audio_response(turn_context, "Ask Country - Placeholder")

    async def _ask_for_gender(self, turn_context: TurnContext):
        print("🎯 Ask: Gender")
        await self._send_audio_response(turn_context, "Ask Gender - Placeholder")

    # === UTILITY METHODS ===

    async def _save_state(self, turn_context: TurnContext):
        """Speichert Bot-States (identisch zum Text-Bot)"""
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)