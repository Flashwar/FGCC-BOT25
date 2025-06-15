import re
from datetime import datetime
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers import NumberParseException, parse, is_valid_number
from asgiref.sync import sync_to_async

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount


from Bot.models import Customer, AddressCountry, AddressStreet, AddressCity, Address, CustomerContact


class DialogState:
    """Definiert die möglichen Zustände innerhalb des Dialogs."""
    GREETING = "greeting"
    ASK_GENDER = "ask_gender"
    ASK_TITLE = "ask_title"
    ASK_FIRST_NAME = "ask_first_name"
    ASK_LAST_NAME = "ask_last_name"
    ASK_BIRTHDATE = "ask_birthdate"
    ASK_EMAIL = "ask_email"
    ASK_PHONE = "ask_phone"
    ASK_STREET = "ask_street"
    ASK_HOUSE_NUMBER = "ask_house_number"
    ASK_HOUSE_ADDITION = "ask_house_addition"
    ASK_POSTAL = "ask_postal"
    ASK_CITY = "ask_city"
    ASK_COUNTRY = "ask_country"
    FINAL_CONFIRMATION = "final_confirmation"
    COMPLETED = "completed"
    ERROR = "error"

    # Bestätigungs-Zustände (dynamisch erstellt für jedes Feld)
    CONFIRM_PREFIX = "confirm_"


class RegistrationBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        self.conversation_state = conversation_state
        self.user_state = user_state

        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")

        self.dialog_handlers = {
            DialogState.GREETING: self._handle_greeting,
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
        }

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

    # --- Vom ActivityHandler überschriebene Methoden ---

    async def on_message_activity(self, turn_context: TurnContext):
        """Wird aufgerufen, wenn eine Nachricht empfangen wird."""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

        user_input = turn_context.activity.text.strip()

        # Bestätigungslogik für alle Felder
        if dialog_state.startswith(DialogState.CONFIRM_PREFIX):
            await self._handle_confirmation(turn_context, user_profile, user_input, dialog_state)
        elif dialog_state in self.dialog_handlers:
            # Rufe den spezifischen Handler auf
            await self.dialog_handlers[dialog_state](turn_context, user_profile, user_input)
        else:
            # Fallback für unbekannte Zustände
            await turn_context.send_activity(MessageFactory.text(
                "Entschuldigung, ich bin verwirrt. Bitte starten Sie neu, indem Sie 'Hallo' sagen."))
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
            # Optional: Zustand zurücksetzen oder eine neue Begrüßung starten
            # await self.user_profile_accessor.set(turn_context, {}) # Profil leeren

        # Zustand nach jeder Runde speichern
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def on_members_added_activity(self, members_added: [ChannelAccount], turn_context: TurnContext):
        """Wird aufgerufen, wenn Mitglieder zur Konversation hinzugefügt werden."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hallo! Ich bin ein Bot, der Ihnen bei der Registrierung hilft.")
                # Initialisiere den Dialog, wenn der Bot der Konversation hinzugefügt wird
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                await self._handle_greeting(turn_context,
                                            await self.user_profile_accessor.get(turn_context, lambda: {}))
                break  # Nur einmal begrüßen, auch wenn mehrere Mitglieder hinzugefügt werden

        # Zustand nach jeder Runde speichern
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    # --- Dialog-Schritt-Handler (Bleiben weitgehend gleich) ---

    async def _handle_greeting(self, turn_context: TurnContext, user_profile, *args):
        """Startet den Registrierungsdialog mit einer Begrüßung."""
        welcome_message = (
            "Hallo! Willkommen bei unserem Kundenregistrierungsbot.\n\n"
            "Ich helfe Ihnen dabei, ein neues Kundenkonto zu erstellen. "
            "Dafür benötige ich einige persönliche Informationen von Ihnen.\n\n"
            "Lassen Sie uns beginnen!"
        )
        await turn_context.send_activity(MessageFactory.text(welcome_message))
        await self._ask_for_gender(turn_context)

    async def _ask_for_gender(self, turn_context: TurnContext):
        """Fragt nach dem Geschlecht des Benutzers."""
        gender_message = (
            "Bitte wählen Sie Ihr Geschlecht:\n\n"
            "1 **Männlich**\n"
            "2 **Weiblich**\n"
            "3 **Divers**\n"
            "4 **Keine Angabe**\n\n"
            "Sie können die Nummer oder den Begriff eingeben."
        )
        await turn_context.send_activity(MessageFactory.text(gender_message))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_GENDER)

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für das Geschlecht."""
        gender_map = {
            "1": ("male", "Männlich"), "männlich": ("male", "Männlich"), "male": ("male", "Männlich"),
            "2": ("female", "Weiblich"), "weiblich": ("female", "Weiblich"), "female": ("female", "Weiblich"),
            "3": ("diverse", "Divers"), "divers": ("diverse", "Divers"), "diverse": ("diverse", "Divers"),
            "4": ("unspecified", "Keine Angabe"), "keine angabe": ("unspecified", "Keine Angabe"),
            "unspecified": ("unspecified", "Keine Angabe"),
        }
        user_input_lower = user_input.lower()
        if user_input_lower in gender_map:
            gender_value, gender_display = gender_map[user_input_lower]
            user_profile['gender'] = gender_value
            user_profile['gender_display'] = gender_display
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Geschlecht", gender_display, DialogState.CONFIRM_PREFIX + "gender")
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte wählen Sie eine gültige Option (1-4) oder geben Sie das Geschlecht direkt ein.")
            )

    async def _ask_for_title(self, turn_context: TurnContext):
        """Fragt nach dem akademischen Titel."""
        title_message = (
            "Haben Sie einen akademischen Titel? (optional)\n\n"
            "**Verfügbare Titel:**\n"
            "• Dr.\n• Prof.\n• Prof. Dr.\n• Prof. Dr. Dr.\n"
            "• Dipl.-Ing.\n• Dr.-Ing.\n• Dr. phil.\n• Dr. jur.\n"
            "• Dr. med.\n• Mag.\n• Lic.\n• Ph.D.\n\n"
            "Geben Sie Ihren Titel ein oder **'kein'** für keinen Titel:"
        )
        await turn_context.send_activity(MessageFactory.text(title_message))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_TITLE)

    async def _handle_title_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für den Titel."""
        valid_titles = [
            "Dr.", "Prof.", "Prof. Dr.", "Prof. Dr. Dr.", "Dipl.-Ing.",
            "Dr.-Ing.", "Dr. phil.", "Dr. jur.", "Dr. med.", "Mag.", "Lic.", "Ph.D."
        ]
        no_title_keywords = ["kein", "keiner", "nein", "keine", "-", "none", ""]

        user_input_strip_lower = user_input.strip().lower()

        if user_input_strip_lower in no_title_keywords:
            user_profile['title'] = ''  # Interner Wert für "Kein Titel" (leer String)
            user_profile['title_display'] = "Kein Titel"  # Für die Anzeige
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Titel", "Kein Titel", DialogState.CONFIRM_PREFIX + "title")
        elif user_input in valid_titles:  # Prüfen, ob die exakte Eingabe in den validen Titeln ist
            user_profile['title'] = user_input  # Interner Wert ist der Titel selbst
            user_profile['title_display'] = user_input  # Für die Anzeige
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Titel", user_input, DialogState.CONFIRM_PREFIX + "title")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte wählen Sie einen gültigen Titel aus der Liste oder geben Sie 'kein' ein.")
            )

    async def _ask_for_first_name(self, turn_context: TurnContext):
        """Fragt nach dem Vornamen."""
        await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihren **Vornamen** ein:"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_FIRST_NAME)

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für den Vornamen."""
        if self._validate_name_part(user_input):
            user_profile['first_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Vorname", user_input, DialogState.CONFIRM_PREFIX + "first_name")
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte geben Sie einen gültigen Vornamen ein (mindestens 2 Zeichen, nur Buchstaben):")
            )

    async def _ask_for_last_name(self, turn_context: TurnContext):
        """Fragt nach dem Nachnamen."""
        await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihren **Nachnamen** ein:"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_LAST_NAME)

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für den Nachnamen."""
        if self._validate_name_part(user_input):
            user_profile['last_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Nachname", user_input, DialogState.CONFIRM_PREFIX + "last_name")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie einen gültigen Nachnamen ein (mindestens 2 Zeichen):")
            )

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        """Fragt nach dem Geburtsdatum."""
        await turn_context.send_activity(
            MessageFactory.text(
                "Bitte geben Sie Ihr **Geburtsdatum** ein (Format: TT.MM.JJJJ):\n\nBeispiel: 15.03.1990")
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für das Geburtsdatum."""
        birthdate = self._validate_birthdate(user_input)
        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Geburtsdatum", user_input,
                                      DialogState.CONFIRM_PREFIX + "birthdate")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie ein gültiges Geburtsdatum im Format TT.MM.JJJJ ein:")
            )

    async def _ask_for_email(self, turn_context: TurnContext):
        """Fragt nach der E-Mail-Adresse."""
        await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihre **E-Mail-Adresse** ein:"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für die E-Mail-Adresse."""
        if self._validate_email(user_input):
            if await self._email_exists_in_db(user_input.strip().lower()):
                await turn_context.send_activity(MessageFactory.text(
                    "Diese E-Mail-Adresse ist bereits registriert. Bitte geben Sie eine andere E-Mail ein."))
                return

            user_profile['email'] = user_input.strip().lower()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "E-Mail", user_input, DialogState.CONFIRM_PREFIX + "email")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige E-Mail-Adresse ein:")
            )

    async def _ask_for_phone(self, turn_context: TurnContext):
        """Fragt nach der Telefonnummer."""
        await turn_context.send_activity(
            MessageFactory.text(
                "Bitte geben Sie Ihre **Telefonnummer** ein:\n\n"
                "Beispiele:\n"
                "• +49 30 12345678\n"
                "• 030 12345678\n"
                "• 0175 1234567"
            )
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_PHONE)

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für die Telefonnummer."""
        phone_number_obj = self._validate_phone(user_input)
        if phone_number_obj:
            user_profile['telephone'] = phone_number_obj.as_e164
            user_profile['telephone_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Telefonnummer", user_input, DialogState.CONFIRM_PREFIX + "phone")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige deutsche Telefonnummer ein:")
            )

    async def _ask_for_street(self, turn_context: TurnContext):
        """Fragt nach der Straße."""
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihre **Straße** ein (ohne Hausnummer):\n\nBeispiel: Musterstraße")
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_STREET)

    async def _handle_street_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für die Straße."""
        if len(user_input.strip()) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['street_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Straße", user_input, DialogState.CONFIRM_PREFIX + "street")
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte geben Sie eine gültige Straße ein (mindestens 3 Zeichen, nur Buchstaben und Leerzeichen):")
            )

    async def _ask_for_house_number(self, turn_context: TurnContext):
        """Fragt nach der Hausnummer."""
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihre **Hausnummer** ein:\n\nBeispiel: 42"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_NUMBER)

    async def _handle_house_number_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für die Hausnummer."""
        try:
            house_number = int(user_input.strip())
            if house_number > 0:
                user_profile['house_number'] = house_number
                await self.user_profile_accessor.set(turn_context, user_profile)
                await self._confirm_field(turn_context, "Hausnummer", str(house_number),
                                          DialogState.CONFIRM_PREFIX + "house_number")
            else:
                raise ValueError()
        except ValueError:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige Hausnummer (positive Zahl) ein:")
            )

    async def _ask_for_house_addition(self, turn_context: TurnContext):
        """Fragt nach dem Hausnummernzusatz."""
        await turn_context.send_activity(
            MessageFactory.text(
                "Haben Sie einen **Hausnummernzusatz**? (optional)\n\n"
                "Beispiele: a, b, 1/2, links\n\n"
                "Geben Sie den Zusatz ein oder **'kein'** für keinen Zusatz:"
            )
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_ADDITION)

    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für den Hausnummernzusatz."""
        if user_input.lower() in ["kein", "keiner", "nein", "keine", "-", ""]:
            user_profile['house_number_addition'] = ""
            user_profile['house_addition_display'] = "Kein Zusatz"
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Hausnummernzusatz", "Kein Zusatz",
                                      DialogState.CONFIRM_PREFIX + "house_addition")
        else:
            user_profile['house_number_addition'] = user_input.strip()
            user_profile['house_addition_display'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Hausnummernzusatz", user_input,
                                      DialogState.CONFIRM_PREFIX + "house_addition")

    async def _ask_for_postal(self, turn_context: TurnContext):
        """Fragt nach der Postleitzahl."""
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihre **Postleitzahl** ein:\n\nBeispiel: 12345"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_POSTAL)

    async def _handle_postal_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für die Postleitzahl."""
        if self._validate_postal_code(user_input):
            user_profile['postal_code'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Postleitzahl", user_input, DialogState.CONFIRM_PREFIX + "postal")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige deutsche Postleitzahl (5 Ziffern) ein:")
            )

    async def _ask_for_city(self, turn_context: TurnContext):
        """Fragt nach dem Ort/Stadt."""
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihren **Ort/Stadt** ein:\n\nBeispiel: Berlin"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CITY)

    async def _handle_city_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für den Ort/Stadt."""
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['city'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Ort", user_input, DialogState.CONFIRM_PREFIX + "city")
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte geben Sie einen gültigen Ort ein (mindestens 2 Zeichen, nur Buchstaben und Leerzeichen):")
            )

    async def _ask_for_country(self, turn_context: TurnContext):
        """Fragt nach dem Land."""
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihr **Land** ein:\n\nBeispiel: Deutschland"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_COUNTRY)

    async def _handle_country_input(self, turn_context: TurnContext, user_profile, user_input):
        """Verarbeitet die Eingabe für das Land."""
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['country_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Land", user_input, DialogState.CONFIRM_PREFIX + "country")
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte geben Sie ein gültiges Land ein (mindestens 2 Zeichen, nur Buchstaben und Leerzeichen):")
            )

    async def _confirm_field(self, turn_context: TurnContext, field_name: str, value: str, confirmation_state: str):
        """Sendet eine Bestätigungsnachricht für ein Feld."""
        confirmation = f"{field_name}: **{value}**\n\nIst das korrekt? (ja/nein)"
        await turn_context.send_activity(MessageFactory.text(confirmation))
        await self.dialog_state_accessor.set(turn_context, confirmation_state)

    async def _handle_confirmation(self, turn_context: TurnContext, user_profile, user_input, dialog_state):
        """
        Behandelt Bestätigungsanfragen und steuert den Dialogfluss basierend auf 'ja'/'nein'.
        """
        user_input_lower = user_input.lower()
        confirmed = user_input_lower in ["ja", "j", "yes", "y", "richtig", "korrekt", "ok"]
        rejected = user_input_lower in ["nein", "n", "no", "falsch", "inkorrekt"]

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
                    await turn_context.send_activity(MessageFactory.text("Okay, lassen Sie uns das korrigieren."))
                    await correction_ask_func(turn_context)
                    found_correction_step = True
                    break
            if not found_correction_step:
                await turn_context.send_activity(
                    MessageFactory.text("Entschuldigung, ich kann diesen Schritt nicht korrigieren."))
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte antworten Sie mit 'ja' oder 'nein'.")
            )

    async def _show_final_summary(self, turn_context: TurnContext):
        """Zeigt eine Zusammenfassung der gesammelten Daten an und bittet um finale Bestätigung."""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})

        title_text = user_profile.get('title_display', 'Kein Titel')
        name_text = f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}"

        address_parts = [user_profile.get('street_name', '')]
        if user_profile.get('house_number'):
            address_parts.append(str(user_profile['house_number']))
        if user_profile.get('house_number_addition'):
            address_parts.append(user_profile['house_number_addition'])
        address_text = " ".join(filter(None, address_parts))

        summary = (
            " **Zusammenfassung Ihrer Angaben:**\n\n"
            f" **Geschlecht:** {user_profile.get('gender_display', 'Nicht angegeben')}\n"
            f" **Titel:** {title_text}\n"
            f" **Name:** {name_text}\n"
            f" **Geburtsdatum:** {user_profile.get('birth_date_display', 'Nicht angegeben')}\n"
            f" **E-Mail:** {user_profile.get('email', 'Nicht angegeben')}\n"
            f" **Telefon:** {user_profile.get('telephone_display', 'Nicht angegeben')}\n"
            f" **Adresse:** {address_text}\n"
            f" **PLZ/Ort:** {user_profile.get('postal_code', 'Nicht angegeben')} {user_profile.get('city', 'Nicht angegeben')}\n"
            f" **Land:** {user_profile.get('country_name', 'Nicht angegeben')}\n\n"
            "Sind alle Angaben korrekt und soll ich das Konto erstellen? (ja/nein)"
        )

        await turn_context.send_activity(MessageFactory.text(summary))
        await self.dialog_state_accessor.set(turn_context, DialogState.FINAL_CONFIRMATION)

    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """Behandelt die finale Bestätigung und speichert die Daten."""
        user_input_lower = user_input.lower()
        if user_input_lower in ["ja", "j", "yes", "y", "richtig", "korrekt", "ok"]:
            success = await self._save_customer_data(user_profile)
            if success:
                await turn_context.send_activity("Ihre Daten wurden erfolgreich gespeichert! Ihr Konto wurde erstellt.")
                await turn_context.send_activity(
                    "Vielen Dank für Ihre Registrierung! Sie können mich jederzeit erneut ansprechen, wenn Sie Fragen haben.")
                await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
                await self.user_profile_accessor.set(turn_context, {})
            else:
                await turn_context.send_activity(
                    "Entschuldigung, beim Speichern Ihrer Daten ist ein Problem aufgetreten. Bitte versuchen Sie es später erneut."
                )
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        elif user_input_lower in ["nein", "n", "no", "falsch", "inkorrekt"]:
            await turn_context.send_activity("Registrierung abgebrochen. Sie können jederzeit neu starten.")
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
            await self.user_profile_accessor.set(turn_context, {})
        else:
            await turn_context.send_activity("Bitte antworten Sie mit 'ja' oder 'nein'.")

    # --- Validierungsmethoden ---

    def _validate_name_part(self, name: str) -> bool:
        """Validiert Vornamen und Nachnamen."""
        return len(name.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\']+$', name.strip()) is not None

    def _validate_birthdate(self, date_str: str) -> datetime | None:
        """Validiert das Geburtsdatum (TT.MM.JJJJ) und das Alter."""
        try:
            date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
            today = datetime.now().date()
            if date_obj < today and (today.year - date_obj.year) < 150:
                return date_obj
        except ValueError:
            pass
        return None

    def _validate_email(self, email: str) -> bool:
        """Validiert eine E-Mail-Adresse."""
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    async def _email_exists_in_db(self, email: str) -> bool:
        """Prüft asynchron, ob eine E-Mail bereits in der Datenbank existiert."""
        return await sync_to_async(CustomerContact.objects.filter(email=email).exists)()

    def _validate_phone(self, phone_str: str) -> PhoneNumber | None:
        """Validiert eine deutsche Telefonnummer und gibt ein PhoneNumber-Objekt zurück."""
        try:
            parsed_number = parse(phone_str, "DE")
            if is_valid_number(parsed_number):
                return PhoneNumber.from_string(phone_str, region="DE")
        except NumberParseException:
            pass
        return None

    def _validate_postal_code(self, postal_code: str) -> bool:
        """Validiert eine deutsche Postleitzahl (5 Ziffern)."""
        return re.match(r'^\d{5}$', postal_code.strip()) is not None

    # --- Datenbank-Speicherlogik (asynchron) ---

    async def _save_customer_data(self, user_profile: dict) -> bool:
        """
        Speichert die gesammelten Benutzerdaten in den Django-Modellen.
        Alle Datenbankoperationen sind asynchron umschlossen.
        """
        try:
            async def _get_or_create(model, **kwargs):
                return await sync_to_async(model.objects.get_or_create)(**kwargs)

            async def _create(model, **kwargs):
                return await sync_to_async(model.objects.create)(**kwargs)

            country_obj, _ = await _get_or_create(
                AddressCountry, country_name=user_profile['country_name']
            )

            street_obj, _ = await _get_or_create(
                AddressStreet, street_name=user_profile['street_name']
            )

            city_obj, _ = await _get_or_create(
                AddressCity,
                city=user_profile['city'],
                postal_code=user_profile['postal_code'],
                country=country_obj
            )

            address_obj = await _create(
                Address,
                street=street_obj,
                house_number=user_profile['house_number'],
                house_number_addition=user_profile.get('house_number_addition', ''),
                place=city_obj
            )

            birth_date_obj = datetime.strptime(user_profile['birth_date'], "%Y-%m-%d").date()

            django_gender_map = {label: value for value, label in Customer.GenderChoice.choices}
            gender_display = user_profile.get('gender_display')
            django_gender = django_gender_map.get(gender_display)

            customer = await _create(
                Customer,
                gender=django_gender,
                first_name=user_profile['first_name'],
                second_name=user_profile['last_name'],
                birth_date=birth_date_obj,
                title=user_profile.get('title', ''),
                address=address_obj
            )

            telephone_to_save = user_profile.get('telephone')
            if not isinstance(telephone_to_save, PhoneNumber):
                # Wenn nicht, erstelle ein Dummy-PhoneNumber-Objekt
                # Wichtig: Die Dummy-Nummer muss gültig sein und dem PhoneNumberField-Format entsprechen.
                try:
                    dummy_phone = PhoneNumber.from_string("+491234567890",
                                                          region="DE")  # Oder eine andere gültige Dummy-Nummer
                    telephone_to_save = dummy_phone
                except NumberParseException:
                    # Fallback, sollte bei einer festen Dummy-Nummer nicht passieren
                    print("FEHLER: Konnte Dummy-Telefonnummer nicht parsen.")
                    return False


            await _create(
                CustomerContact,
                customer=customer,
                email=user_profile['email'],
                telephone=telephone_to_save
            )

            print(f"Customer {customer.customer_id} and contact saved successfully!")
            return True

        except Exception as e:
            print(f"Error saving data to database: {e}")
            import traceback
            traceback.print_exc()
            return False