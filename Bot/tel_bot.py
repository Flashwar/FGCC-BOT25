# bot/simplified_audio_bot.py
import aiohttp
import tempfile
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from phonenumbers import NumberParseException, parse, is_valid_number
from asgiref.sync import sync_to_async

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount, Attachment, ActivityTypes
from Bot.azure_service.luis_service import AzureCLUService
from Bot.azure_service.speech_service import AzureSpeechService
from Bot.models import Customer, AddressCountry, AddressStreet, AddressCity, Address, CustomerContact

print("=== VEREINFACHTER AUDIO BOT WIRD GELADEN ===")


class SimplifiedAudioStates:
    """Vereinfachte States für den Sprachfluss"""
    START = "start"
    ASK_NAME = "ask_name"
    ASK_BIRTHDATE = "ask_birthdate"
    ASK_EMAIL = "ask_email"
    ASK_PHONE = "ask_phone"
    ASK_ADDRESS = "ask_address"
    ASK_POSTAL_CITY = "ask_postal_city"
    ASK_COUNTRY = "ask_country"
    FINAL_VALIDATION = "final_validation"
    SAVE_DATA = "save_data"
    COMPLETED = "completed"
    ERROR = "error"


class SimplifiedAudioBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        super().__init__()
        print("🎤 Initialisiere Vereinfachten Audio Bot...")

        # States
        self.conversation_state = conversation_state
        self.user_state = user_state

        # State Accessors
        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")

        # Azure Services initialisieren
        try:
            # Importiere deine Settings richtig
            from FCCSemesterAufgabe.settings import KEYVAULT_SERVICE, isDocker
            self.keyvault = KEYVAULT_SERVICE

            if not isDocker:
                self.clu_service = AzureCLUService(self.keyvault)
                self.speech_service = AzureSpeechService(self.keyvault)
                print("✅ Azure Services erfolgreich initialisiert")
            else:
                print("⚠️ KeyVault Service nicht verfügbar - verwende Mock Services")
                self.clu_service = None
                self.speech_service = None

        except Exception as e:
            print(f"⚠️ Azure Services nicht verfügbar: {e}")
            print("🔄 Verwende Mock Services für Tests")
            self.clu_service = None
            self.speech_service = None

        # Unterstützte Audio-Formate
        self.supported_audio_types = {
            'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp3', 'audio/x-wav', 'audio/wave'
        }

        # State Handler Mapping
        self.state_handlers = {
            SimplifiedAudioStates.START: self._handle_start,
            SimplifiedAudioStates.ASK_NAME: self._handle_name_input,
            SimplifiedAudioStates.ASK_BIRTHDATE: self._handle_birthdate_input,
            SimplifiedAudioStates.ASK_EMAIL: self._handle_email_input,
            SimplifiedAudioStates.ASK_PHONE: self._handle_phone_input,
            SimplifiedAudioStates.ASK_ADDRESS: self._handle_address_input,
            SimplifiedAudioStates.ASK_POSTAL_CITY: self._handle_postal_city_input,
            SimplifiedAudioStates.ASK_COUNTRY: self._handle_country_input,
            SimplifiedAudioStates.FINAL_VALIDATION: self._handle_final_validation,
        }

        print("✅ Vereinfachter Audio Bot initialisiert")

    async def on_message_activity(self, turn_context: TurnContext):
        """Verarbeitet eingehende Audio-Nachrichten."""
        print("\n" + "=" * 50)
        print("🎤 AUDIO MESSAGE - VEREINFACHTER FLOW")
        print("=" * 50)

        try:
            attachments = turn_context.activity.attachments or []
            audio_attachments = [att for att in attachments if att.content_type in self.supported_audio_types]

            if not audio_attachments:
                await self._send_audio_only_message(turn_context)
                return

            # Audio verarbeiten
            attachment = audio_attachments[0]
            await self._process_audio_message(turn_context, attachment)

        except Exception as e:
            print(f"❌ Fehler in on_message_activity: {e}")
            await self._send_audio_response(turn_context,
                                            "Entschuldigung, es gab einen Fehler beim Verarbeiten Ihrer Nachricht.")

        # State speichern
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def _process_audio_message(self, turn_context: TurnContext, attachment: Attachment):
        """Verarbeitet Audio-Nachricht gemäß Sprachfluss."""
        try:
            # 1. Audio herunterladen
            audio_bytes = await self._download_audio(attachment)
            if not audio_bytes:
                await self._send_audio_response(turn_context, "Ich konnte die Audio-Datei nicht laden.")
                return

            # 2. Speech-to-Text
            stt_result = self.speech_service.speech_to_text_from_bytes(audio_bytes)
            if not stt_result.get('success'):
                await self._send_audio_response(turn_context,
                                                "Entschuldigung, ich konnte Ihre Sprache nicht verstehen. Bitte sprechen Sie deutlicher.")
                return

            recognized_text = stt_result.get('text', '').strip()
            print(f"🗣️ Erkannter Text: '{recognized_text}'")

            if not recognized_text:
                await self._send_audio_response(turn_context,
                                                "Ich habe nichts verstanden. Bitte sprechen Sie lauter.")
                return

            # 3. CLU Analyse (für besseres Verständnis)
            try:
                clu_result = await self.clu_service.analyze_conversation(recognized_text)
                print(f"🧠 CLU: {clu_result.get('total_intents_found', 0)} Intents gefunden")
            except Exception as e:
                print(f"⚠️ CLU Fehler: {e}")

            # 4. Dialog-State basierte Verarbeitung
            user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
            dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: SimplifiedAudioStates.START)

            # State Handler aufrufen
            if dialog_state in self.state_handlers:
                await self.state_handlers[dialog_state](turn_context, user_profile, recognized_text)
            else:
                await self._handle_start(turn_context, user_profile, recognized_text)

        except Exception as e:
            print(f"❌ Fehler in _process_audio_message: {e}")
            await self._send_audio_response(turn_context, "Bei der Verarbeitung ist ein Fehler aufgetreten.")

    # === STATE HANDLERS (Sprachfluss) ===

    async def _handle_start(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Start der Konversation - Begrüßung & Erklärung des Ziels"""
        welcome_text = (
            "Hallo! Willkommen bei unserem Sprach-Registrierungsbot. "
            "Ich helfe Ihnen dabei, ein neues Kundenkonto zu erstellen. "
            "Dafür benötige ich einige persönliche Informationen von Ihnen. "
            "Lassen Sie uns mit Ihrem Namen beginnen."
        )
        await self._send_audio_response(turn_context, welcome_text)
        await self._ask_for_name(turn_context)

    async def _ask_for_name(self, turn_context: TurnContext):
        """Frage nach Vor- und Nachname"""
        await self._send_audio_response(turn_context,
                                        "Bitte sagen Sie mir Ihren vollständigen Namen, also Vor- und Nachname.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_NAME)

    async def _handle_name_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung der Namenseingabe"""
        # Einfache Namensextraktion (Vor- und Nachname)
        name_parts = user_input.strip().split()

        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])

            if self._validate_name_part(first_name) and self._validate_name_part(last_name):
                user_profile['first_name'] = first_name
                user_profile['last_name'] = last_name
                await self.user_profile_accessor.set(turn_context, user_profile)

                # Bestätigung
                confirmation = f"Ich habe verstanden: {first_name} {last_name}. Ist das korrekt?"
                await self._send_audio_response(turn_context, confirmation)

                # Warte auf Bestätigung oder gehe weiter
                await self._ask_for_birthdate(turn_context)
            else:
                await self._send_audio_response(turn_context,
                                                "Der Name wurde nicht korrekt verstanden. Bitte sagen Sie Ihren vollständigen Namen noch einmal deutlich.")
        else:
            await self._send_audio_response(turn_context,
                                            "Bitte sagen Sie sowohl Ihren Vor- als auch Nachnamen.")

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        """Frage nach Geburtsdatum"""
        await self._send_audio_response(turn_context,
                                        "Nun benötige ich Ihr Geburtsdatum. Bitte sagen Sie es im Format Tag, Monat, Jahr. "
                                        "Zum Beispiel: fünfzehnter März neunzehnhundert neunzig.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung der Geburtsdatumseingabe"""
        birthdate = self._extract_birthdate_from_text(user_input)

        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = birthdate.strftime('%d.%m.%Y')
            await self.user_profile_accessor.set(turn_context, user_profile)

            confirmation = f"Ihr Geburtsdatum ist der {birthdate.strftime('%d.%m.%Y')}. Ist das richtig?"
            await self._send_audio_response(turn_context, confirmation)
            await self._ask_for_email(turn_context)
        else:
            await self._send_audio_response(turn_context,
                                            "Das Geburtsdatum wurde nicht korrekt verstanden. Bitte sagen Sie es noch einmal, "
                                            "zum Beispiel: fünfter Mai neunzehnhundert achtzig.")

    async def _ask_for_email(self, turn_context: TurnContext):
        """Frage nach E-Mail-Adresse"""
        await self._send_audio_response(turn_context,
                                        "Jetzt benötige ich Ihre E-Mail-Adresse. Bitte buchstabieren Sie sie deutlich.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung der E-Mail-Eingabe"""
        email = self._extract_email_from_text(user_input)

        if email and self._validate_email(email):
            if await self._email_exists_in_db(email):
                await self._send_audio_response(turn_context,
                                                "Diese E-Mail-Adresse ist bereits registriert. Bitte geben Sie eine andere E-Mail-Adresse an.")
                return

            user_profile['email'] = email
            await self.user_profile_accessor.set(turn_context, user_profile)

            confirmation = f"Ihre E-Mail-Adresse ist {email}. Ist das korrekt?"
            await self._send_audio_response(turn_context, confirmation)
            await self._ask_for_phone(turn_context)
        else:
            await self._send_audio_response(turn_context,
                                            "Die E-Mail-Adresse wurde nicht korrekt verstanden. Bitte buchstabieren Sie sie noch einmal deutlich.")

    async def _ask_for_phone(self, turn_context: TurnContext):
        """Frage nach Telefonnummer"""
        await self._send_audio_response(turn_context,
                                        "Nun benötige ich Ihre Telefonnummer. Bitte sagen Sie die Ziffern einzeln und deutlich.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_PHONE)

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung der Telefonnummereingabe"""
        phone = self._extract_phone_from_text(user_input)

        if phone and self._validate_phone(phone):
            user_profile['telephone'] = phone
            user_profile['telephone_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            confirmation = f"Ihre Telefonnummer ist {phone}. Ist das richtig?"
            await self._send_audio_response(turn_context, confirmation)
            await self._ask_for_address(turn_context)
        else:
            await self._send_audio_response(turn_context,
                                            "Die Telefonnummer wurde nicht korrekt verstanden. Bitte sagen Sie die Ziffern noch einmal einzeln.")

    async def _ask_for_address(self, turn_context: TurnContext):
        """Frage nach Straße und Hausnummer"""
        await self._send_audio_response(turn_context,
                                        "Jetzt benötige ich Ihre Adresse. Bitte sagen Sie mir Straße und Hausnummer.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_ADDRESS)

    async def _handle_address_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung der Adresseingabe"""
        street, house_number = self._extract_street_and_number(user_input)

        if street and house_number:
            user_profile['street_name'] = street
            user_profile['house_number'] = house_number
            user_profile['house_number_addition'] = ""
            await self.user_profile_accessor.set(turn_context, user_profile)

            confirmation = f"Ihre Adresse ist {street} {house_number}. Ist das korrekt?"
            await self._send_audio_response(turn_context, confirmation)
            await self._ask_for_postal_city(turn_context)
        else:
            await self._send_audio_response(turn_context,
                                            "Die Adresse wurde nicht korrekt verstanden. Bitte sagen Sie Straße und Hausnummer noch einmal.")

    async def _ask_for_postal_city(self, turn_context: TurnContext):
        """Frage nach PLZ und Ort"""
        await self._send_audio_response(turn_context,
                                        "Nun benötige ich Ihre Postleitzahl und Ihren Wohnort.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_POSTAL_CITY)

    async def _handle_postal_city_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung von PLZ und Ort"""
        postal_code, city = self._extract_postal_and_city(user_input)

        if postal_code and city:
            user_profile['postal_code'] = postal_code
            user_profile['city'] = city
            await self.user_profile_accessor.set(turn_context, user_profile)

            confirmation = f"Postleitzahl {postal_code}, Ort {city}. Ist das richtig?"
            await self._send_audio_response(turn_context, confirmation)
            await self._ask_for_country(turn_context)
        else:
            await self._send_audio_response(turn_context,
                                            "Postleitzahl und Ort wurden nicht korrekt verstanden. Bitte wiederholen Sie beides.")

    async def _ask_for_country(self, turn_context: TurnContext):
        """Frage nach Land"""
        await self._send_audio_response(turn_context,
                                        "Abschließend benötige ich noch Ihr Land.")
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.ASK_COUNTRY)

    async def _handle_country_input(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Verarbeitung der Ländereingabe"""
        country = user_input.strip().title()

        if len(country) >= 2:
            user_profile['country_name'] = country
            await self.user_profile_accessor.set(turn_context, user_profile)

            confirmation = f"Ihr Land ist {country}. Ist das korrekt?"
            await self._send_audio_response(turn_context, confirmation)
            await self._final_validation(turn_context)
        else:
            await self._send_audio_response(turn_context,
                                            "Das Land wurde nicht korrekt verstanden. Bitte sagen Sie es noch einmal.")

    async def _final_validation(self, turn_context: TurnContext):
        """Finale Validierung aller Daten"""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})

        # Alle Daten zusammenfassen
        summary = (
            f"Vielen Dank! Hier ist eine Zusammenfassung Ihrer Angaben: "
            f"Name: {user_profile.get('first_name')} {user_profile.get('last_name')}, "
            f"Geburtsdatum: {user_profile.get('birth_date_display')}, "
            f"E-Mail: {user_profile.get('email')}, "
            f"Telefon: {user_profile.get('telephone')}, "
            f"Adresse: {user_profile.get('street_name')} {user_profile.get('house_number')}, "
            f"Postleitzahl und Ort: {user_profile.get('postal_code')} {user_profile.get('city')}, "
            f"Land: {user_profile.get('country_name')}. "
            f"Sind alle Angaben korrekt und soll ich Ihr Konto erstellen?"
        )

        await self._send_audio_response(turn_context, summary)
        await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.FINAL_VALIDATION)

    async def _handle_final_validation(self, turn_context: TurnContext, user_profile: dict, user_input: str):
        """Behandlung der finalen Bestätigung"""
        user_input_lower = user_input.lower()

        if any(word in user_input_lower for word in ["ja", "yes", "richtig", "korrekt", "okay", "ok"]):
            # Daten speichern
            success = await self._save_customer_data(user_profile)

            if success:
                await self._send_audio_response(turn_context,
                                                "Perfekt! Ihre Daten wurden erfolgreich gespeichert und Ihr Konto wurde erstellt. "
                                                "Vielen Dank für Ihre Registrierung!")
                await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.COMPLETED)
            else:
                await self._send_audio_response(turn_context,
                                                "Entschuldigung, beim Speichern ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.")

        elif any(word in user_input_lower for word in ["nein", "no", "falsch", "inkorrekt"]):
            await self._send_audio_response(turn_context,
                                            "Verstanden. Die Registrierung wurde abgebrochen. Sie können jederzeit neu starten.")
            await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.START)
            await self.user_profile_accessor.set(turn_context, {})

        else:
            await self._send_audio_response(turn_context,
                                            "Bitte antworten Sie mit ja oder nein.")

    # === HILFSMETHODEN ===

    async def _download_audio(self, attachment: Attachment) -> bytes:
        """Lädt Audio-Attachment herunter"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.content_url) as response:
                    if response.status == 200:
                        return await response.read()
            return None
        except Exception as e:
            print(f"❌ Download Error: {e}")
            return None

    async def _send_audio_response(self, turn_context: TurnContext, text: str):
        """Sendet Antwort als Audio"""
        try:
            audio_bytes = self.speech_service.text_to_speech_bytes(text)

            if audio_bytes:
                import base64
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

                attachment = Attachment(
                    content_type="audio/wav",
                    content_url=f"data:audio/wav;base64,{audio_base64}",
                    name="bot_response.wav"
                )

                reply = MessageFactory.attachment(attachment)
                reply.text = f"🔊 {text}"
                await turn_context.send_activity(reply)
            else:
                await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))

        except Exception as e:
            print(f"❌ Audio Response Error: {e}")
            await turn_context.send_activity(MessageFactory.text(f"🔊 {text}"))

    async def _send_audio_only_message(self, turn_context: TurnContext):
        """Hinweis für Nur-Audio-Modus"""
        await self._send_audio_response(turn_context,
                                        "Hallo! Ich bin ein Sprach-Bot. Bitte senden Sie mir eine Sprachnachricht für die Registrierung.")

    # === VALIDIERUNGS- UND EXTRAKTIONSMETHODEN ===

    def _validate_name_part(self, name: str) -> bool:
        """Validiert Namensteil"""
        return len(name.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\']+$', name.strip())

    def _extract_birthdate_from_text(self, text: str) -> Optional[datetime]:
        """Extrahiert Geburtsdatum aus gesprochenem Text"""
        try:
            # Vereinfachte Extraktion - sollte erweitert werden
            import re
            date_patterns = [
                r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
                r'(\d{1,2}) (\d{1,2}) (\d{4})',
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    day, month, year = map(int, match.groups())
                    return datetime(year, month, day)

            return None
        except:
            return None

    def _extract_email_from_text(self, text: str) -> Optional[str]:
        """Extrahiert E-Mail aus gesprochenem Text"""
        import re
        # Einfache E-Mail-Extraktion
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group() if match else None

    def _extract_phone_from_text(self, text: str) -> Optional[str]:
        """Extrahiert Telefonnummer aus gesprochenem Text"""
        import re
        # Entferne Leerzeichen und extrahiere Ziffern
        digits = re.sub(r'[^\d+]', '', text)
        return digits if len(digits) >= 10 else None

    def _extract_street_and_number(self, text: str) -> tuple:
        """Extrahiert Straße und Hausnummer"""
        import re
        # Vereinfachte Extraktion
        match = re.search(r'(.+?)\s+(\d+[a-zA-Z]?)$', text.strip())
        if match:
            return match.group(1).strip(), match.group(2)
        return None, None

    def _extract_postal_and_city(self, text: str) -> tuple:
        """Extrahiert PLZ und Stadt"""
        import re
        match = re.search(r'(\d{5})\s+(.+)', text.strip())
        if match:
            return match.group(1), match.group(2).strip()
        return None, None

    def _validate_email(self, email: str) -> bool:
        """Validiert E-Mail"""
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def _validate_phone(self, phone: str) -> bool:
        """Validiert Telefonnummer"""
        try:
            parsed = parse(phone, "DE")
            return is_valid_number(parsed)
        except NumberParseException:
            return False

    async def _email_exists_in_db(self, email: str) -> bool:
        """Prüft E-Mail in DB"""
        return await sync_to_async(CustomerContact.objects.filter(email=email).exists)()

    async def _save_customer_data(self, user_profile: dict) -> bool:
        """Speichert Kundendaten in DB"""
        try:
            # Vereinfachte Speicherung - nutze die Logik vom ursprünglichen Bot
            async def _get_or_create(model, **kwargs):
                return await sync_to_async(model.objects.get_or_create)(**kwargs)

            async def _create(model, **kwargs):
                return await sync_to_async(model.objects.create)(**kwargs)

            # Country
            country_obj, _ = await _get_or_create(
                AddressCountry, country_name=user_profile['country_name']
            )

            # Street
            street_obj, _ = await _get_or_create(
                AddressStreet, street_name=user_profile['street_name']
            )

            # City
            city_obj, _ = await _get_or_create(
                AddressCity,
                city=user_profile['city'],
                postal_code=user_profile['postal_code'],
                country=country_obj
            )

            # Address
            address_obj = await _create(
                Address,
                street=street_obj,
                house_number=int(user_profile['house_number']),
                house_number_addition=user_profile.get('house_number_addition', ''),
                place=city_obj
            )

            # Customer
            birth_date = datetime.strptime(user_profile['birth_date'], "%Y-%m-%d").date()
            customer = await _create(
                Customer,
                gender='unspecified',  # Vereinfacht
                first_name=user_profile['first_name'],
                second_name=user_profile['last_name'],
                birth_date=birth_date,
                title='',
                address=address_obj
            )

            # Contact
            from phonenumber_field.phonenumber import PhoneNumber
            phone_obj = PhoneNumber.from_string(user_profile['telephone'], region="DE")

            await _create(
                CustomerContact,
                customer=customer,
                email=user_profile['email'],
                telephone=phone_obj
            )

            print(f"✅ Customer {customer.customer_id} erfolgreich gespeichert!")
            return True

        except Exception as e:
            print(f"❌ Speicherfehler: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        """Begrüßung für neue Mitglieder"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self.dialog_state_accessor.set(turn_context, SimplifiedAudioStates.START)
                await self._handle_start(turn_context, {}, "")
                break

        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)