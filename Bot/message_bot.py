import re

from datetime import datetime
from injector import inject

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount

from .validators import DataValidator
from .services import CustomerService

class DialogState:
    """Defines the possible states within the conversation flow"""
    GREETING = "greeting"
    ASK_CONSENT = "ask_consent"
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

    ## Confirmation states (dynamically created for each field, e.g., 'confirm_gender')
    CONFIRM_PREFIX = "confirm_"


class RegistrationTextBot(ActivityHandler):
    """Initializes the RegistrationTextBot"""
    @inject
    def __init__(self, conversation_state: ConversationState, user_state: UserState, customer_service: CustomerService):
        self.customer_service = customer_service
        self.conversation_state = conversation_state
        self.user_state = user_state

        # Accessors for storing and retrieving user profile and dialogue state data
        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")

        # Dictionary mapping dialogue states to their respective handler methods
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
        # Defines the linear flow of the dialogue, including confirmation steps
        # Each tuple: (confirmation_state, next_question_if_confirmed, re-ask_question_if_not_confirmed)
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

    async def on_message_activity(self, turn_context: TurnContext):
        # Called when a message activity is received from the user

        # Retrieve user profile and current dialogue state. If not set, initialize to empty dict or GREETING.
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

        user_input = turn_context.activity.text.strip()
        user_input_lower = user_input.lower()

        # Auto-start registration for first-time users
        if not user_profile and dialog_state == DialogState.GREETING:
            # Mark as first interaction and show welcome
            user_profile['first_interaction'] = True
            await self.user_profile_accessor.set(turn_context, user_profile)

            await self._handle_greeting(turn_context, user_profile)

            # Save state and return early
            await self.conversation_state.save_changes(turn_context)
            await self.user_state.save_changes(turn_context)
            return

        # Special handling for the COMPLETED state, where the registration is finished
        if dialog_state == DialogState.COMPLETED:
            await self._handle_completed_state(turn_context, user_profile, user_input)
        # Handle the state where the user is selecting a field to correct
        elif dialog_state == "correction_selection":
            await self._handle_correction_selection(turn_context, user_profile, user_input)
        # Handle the state where the user is selecting a field to correct
        elif dialog_state.startswith(DialogState.CONFIRM_PREFIX):
            await self._handle_confirmation(turn_context, user_profile, user_input, dialog_state)
        elif dialog_state in self.dialog_handlers:
            # Handle confirmation logic for any field
            await self.dialog_handlers[dialog_state](turn_context, user_profile, user_input)
        else:
            # Fallback for unknown or unhandled states
            # should not be possible
            await self._handle_unknown_state(turn_context, user_profile, user_input)

        # save the state after each iteration
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)


    async def _start_correction_process(self, turn_context: TurnContext, user_profile):
        # Starts the correction process by displaying a list of fields the user can choose to modify

        correction_options = (
            "**Welche Daten möchten Sie korrigieren?**\n\n"
            "**Wählen Sie eine Nummer oder den Namen:**\n"
            "**1.** Geschlecht\n"
            "**2.** Titel\n"
            "**3.** Vorname\n"
            "**4.** Nachname\n"
            "**5.** Geburtsdatum\n"
            "**6.** E-Mail\n"
            "**7.** Telefon\n"
            "**8.** Straße\n"
            "**9.** Hausnummer\n"
            "**10.** Hausnummernzusatz\n"
            "**11.** PLZ\n"
            "**12.** Ort\n"
            "**13.** Land\n\n"
            "**Beispiele:**\n"
            "• '6' oder 'Email' - um E-Mail zu ändern\n"
            "• '8' oder 'Straße' - um Straße zu korrigieren\n\n"
            "**Oder sagen Sie:**\n"
            "• **'Zurück'** - zur Zusammenfassung\n"
            "• **'Neustart'** - komplett von vorne"
        )

        await turn_context.send_activity(MessageFactory.text(correction_options))
        # Set the dialogue state to indicate that the bot is waiting for a correction selection
        await self.dialog_state_accessor.set(turn_context, "correction_selection")

    async def _handle_correction_selection(self, turn_context: TurnContext, user_profile, user_input):
        #  Handles the user's selection of which field to correct
        user_input_lower = user_input.lower().strip()

        # Mapping of user input (numbers and text) to the corresponding dialogue states
        # for asking the specific field

        # Number mapping
        correction_mapping = {
            "1": DialogState.ASK_GENDER,
            "2": DialogState.ASK_TITLE,
            "3": DialogState.ASK_FIRST_NAME,
            "4": DialogState.ASK_LAST_NAME,
            "5": DialogState.ASK_BIRTHDATE,
            "6": DialogState.ASK_EMAIL,
            "7": DialogState.ASK_PHONE,
            "8": DialogState.ASK_STREET,
            "9": DialogState.ASK_HOUSE_NUMBER,
            "10": DialogState.ASK_HOUSE_ADDITION,
            "11": DialogState.ASK_POSTAL,
            "12": DialogState.ASK_CITY,
            "13": DialogState.ASK_COUNTRY,

            # text based mapping
            "geschlecht": DialogState.ASK_GENDER,
            "titel": DialogState.ASK_TITLE,
            "vorname": DialogState.ASK_FIRST_NAME,
            "nachname": DialogState.ASK_LAST_NAME,
            "name": DialogState.ASK_FIRST_NAME,
            "geburtsdatum": DialogState.ASK_BIRTHDATE,
            "geburtstag": DialogState.ASK_BIRTHDATE,
            "email": DialogState.ASK_EMAIL,
            "e-mail": DialogState.ASK_EMAIL,
            "mail": DialogState.ASK_EMAIL,
            "telefon": DialogState.ASK_PHONE,
            "phone": DialogState.ASK_PHONE,
            "handy": DialogState.ASK_PHONE,
            "straße": DialogState.ASK_STREET,
            "strasse": DialogState.ASK_STREET,
            "adresse": DialogState.ASK_STREET,
            "hausnummer": DialogState.ASK_HOUSE_NUMBER,
            "nummer": DialogState.ASK_HOUSE_NUMBER,
            "hausnummernzusatz": DialogState.ASK_HOUSE_ADDITION,
            "zusatz": DialogState.ASK_HOUSE_ADDITION,
            "plz": DialogState.ASK_POSTAL,
            "postleitzahl": DialogState.ASK_POSTAL,
            "ort": DialogState.ASK_CITY,
            "stadt": DialogState.ASK_CITY,
            "city": DialogState.ASK_CITY,
            "land": DialogState.ASK_COUNTRY,
            "country": DialogState.ASK_COUNTRY
        }

        # Handle special commands like "back" or "restart"
        if user_input_lower in ["zurück", "back", "summary", "zusammenfassung"]:
            await self._show_final_summary(turn_context)
            return

        elif user_input_lower in ["neustart", "restart", "von vorne"]:
            await self._handle_restart_request(turn_context)
            return

        # Process the correction selection by iterating through the mapping
        target_state = None
        selected_field = None

        for key, state in correction_mapping.items():
            # Check if the input contains a valid key
            if key in user_input_lower:
                target_state = state
                selected_field = key
                break

        if target_state:
            # Confirm the selection and jump to the appropriate state for re-entering the data
            field_names = {
                DialogState.ASK_GENDER: "Geschlecht",
                DialogState.ASK_TITLE: "Titel",
                DialogState.ASK_FIRST_NAME: "Vorname",
                DialogState.ASK_LAST_NAME: "Nachname",
                DialogState.ASK_BIRTHDATE: "Geburtsdatum",
                DialogState.ASK_EMAIL: "E-Mail",
                DialogState.ASK_PHONE: "Telefonnummer",
                DialogState.ASK_STREET: "Straße",
                DialogState.ASK_HOUSE_NUMBER: "Hausnummer",
                DialogState.ASK_HOUSE_ADDITION: "Hausnummernzusatz",
                DialogState.ASK_POSTAL: "Postleitzahl",
                DialogState.ASK_CITY: "Ort",
                DialogState.ASK_COUNTRY: "Land"
            }

            # Get display name or default value
            field_display = field_names.get(target_state, "das gewählte Feld")

            # text for the correction message
            correction_start_message = (
                f"**Korrektur: {field_display}**\n\n"
                f"Sie möchten {field_display} ändern."
                f"Bitte geben Sie den neuen Wert ein:"
            )

            # send text
            await turn_context.send_activity(MessageFactory.text(correction_start_message))

            # Set the dialogue state to the target field, prompting for new input
            await self.dialog_state_accessor.set(turn_context, target_state)

            # Mark that the bot is in correction mode and where to return after correction.
            user_profile['correction_mode'] = True
            user_profile['correction_return_to'] = 'final_summary'
            await self.user_profile_accessor.set(turn_context, user_profile)

        else:
            # not understood output text
            help_message = (
                "**Ich habe das nicht verstanden.**\n\n"
                "Bitte wählen Sie:\n"
                "• **Eine Nummer** (1-13)\n"
                "• **Einen Feldnamen** (z.B. 'Email', 'Adresse')\n"
                "• **'Zurück'** zur Zusammenfassung\n"
                "• **'Neustart'** für kompletten Neustart\n\n"
                "**Was möchten Sie korrigieren?**"
            )
            await turn_context.send_activity(MessageFactory.text(help_message))

    async def _handle_restart_request(self, turn_context: TurnContext):
       # Handles requests to restart the entire registration process
        restart_message = (
            "**Neustart wird gestartet...**\n\n"
            "Alle bisherigen Eingaben werden gelöscht und wir beginnen von vorne."
        )
        await turn_context.send_activity(MessageFactory.text(restart_message))


        # Reset user profile and dialogue state to start fresh
        await self.user_profile_accessor.set(turn_context, {})
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

        # start new registration
        await self._handle_greeting(turn_context, {})



    async def _check_correction_mode_and_handle(self, turn_context: TurnContext, user_profile,
                                                field_name, field_display, new_value):
        # Method to handle post-input logic when in correction mode
        #  If in correction mode, it confirms the correction and returns to the summary
        #  Otherwise, it returns False to continue with normal dialogue flow

        if user_profile.get('correction_mode'):
            # Correction completed - confirm and return to summary
            correction_success_message = (
                f"✅ **{field_display} korrigiert!**\n\n"
                f"Neuer Wert: {new_value}\n\n"
                f"Zurück zur Zusammenfassung..."
            )
            await turn_context.send_activity(MessageFactory.text(correction_success_message))

            # exit mode
            user_profile['correction_mode'] = False
            await self.user_profile_accessor.set(turn_context, user_profile)

            # return back to summary
            await self._show_final_summary(turn_context)
            return True  # Indicate that correction mode was active and correct handled

        return False  # Indicate that normal mode should continue

    async def _handle_completed_state(self, turn_context: TurnContext, user_profile, user_input):
        #  Handles messages received when the registration process is in a completed state
        user_input_lower = user_input.lower()

        # Keywords to detect if the user wants to start a new registration
        restart_keywords = [
            'hallo', 'hello', 'hi', 'neu', 'nochmal', 'wieder', 'start',
            'registrierung', 'anmelden', 'beginnen', 'restart', 'new'
        ]

        if any(keyword in user_input_lower for keyword in restart_keywords):
            # Check if the previous registration was cancelled
            if user_profile.get('registration_cancelled'):
                restart_message = (
                    "**Neue Registrierung starten**\n\n"
                    "Möchten Sie es nochmal versuchen? Ich starte gerne eine neue Registrierung für Sie.\n\n"
                    "Hier nochmal die Information zu unserem Prozess:"
                )
                await turn_context.send_activity(MessageFactory.text(restart_message))

                # reset and restart registration
                await self.user_profile_accessor.set(turn_context, {})
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

                # Start the new registration
                await self._handle_greeting(turn_context, {})

            elif user_profile.get('consent_given') and not user_profile.get('registration_cancelled'):
                # Registration was successful
                success_message = (
                    "**Registrierung bereits abgeschlossen**\n\n"
                    "Sie haben sich bereits erfolgreich registriert! "
                    "Falls Sie Änderungen vornehmen möchten, wenden Sie sich bitte an unseren Support.\n\n"
                    "Haben Sie noch andere Fragen?"
                )
                await turn_context.send_activity(MessageFactory.text(success_message))
        else:
            # Other inquiries after registration is completed
            if user_profile.get('registration_cancelled'):
                help_message = (
                    "**Registrierung wurde abgebrochen**\n\n"
                    "Falls Sie Ihre Meinung geändert haben, sagen Sie einfach:\n"
                    "• **'Hallo'** oder **'Neu'** - um eine neue Registrierung zu starten\n\n"
                    "Ansonsten helfe ich Ihnen gerne bei anderen Fragen."
                )
            else:
                help_message = (
                    "**Registrierung bereits abgeschlossen**\n\n"
                    "Ihre Registrierung war erfolgreich! Bei Fragen wenden Sie sich bitte an unseren Support.\n\n"
                    "Oder sagen Sie **'Hallo'** um eine neue Registrierung für eine andere Person zu starten."
                )

            await turn_context.send_activity(MessageFactory.text(help_message))

    async def _handle_unknown_state(self, turn_context: TurnContext, user_profile, user_input):
      #  Handles situations where the bot is in an unknown or unexpected dialogue state
      # try to bring back a known state or worse, restart the process
        user_input_lower = user_input.lower()

        # check for the restart keywords
        restart_keywords = ['hallo', 'hello', 'hi', 'start', 'neu', 'beginnen']

        if any(keyword in user_input_lower for keyword in restart_keywords):
            # user wants a restart
            restart_message = (
                "**Neustart erkannt**\n\n"
                "Ich starte eine neue Registrierung für Sie."
            )
            await turn_context.send_activity(MessageFactory.text(restart_message))

            # reset state and set to registration beginning
            await self.user_profile_accessor.set(turn_context, {})
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

            # start new registration
            await self._handle_greeting(turn_context, {})
        else:
            # Unknown state + no restart keywords
            confusion_message = (
                "**Entschuldigung, ich bin verwirrt.**\n\n"
                "Es scheint ein Problem mit dem Dialog-Verlauf aufgetreten zu sein.\n\n"
                "Sagen Sie einfach **'Hallo'** um eine neue Registrierung zu beginnen."
            )
            await turn_context.send_activity(MessageFactory.text(confusion_message))

            # Reset state to COMPLETED, but do NOT automatically start a new registration
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)

    async def on_members_added_activity(self, members_added: [ChannelAccount], turn_context: TurnContext):
        """Called when members are added to the conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                # Initialize dialog state and start registration
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                await self._handle_greeting(turn_context,
                                            await self.user_profile_accessor.get(turn_context, lambda: {}))

                break  # Only greet once, even if multiple members are added

        # Save state after each round
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)


    async def _handle_greeting(self, turn_context: TurnContext, user_profile, *args):
        # Starts the registration dialogue with a welcome message and explanation of the process
        welcome_message = (
            "**Willkommen bei unserem Kundenregistrierungsbot!**\n\n"
            "Ich helfe Ihnen dabei, ein neues Kundenkonto zu erstellen. "
            "Dafür benötige ich einige persönliche Informationen von Ihnen:\n\n"
            "**Was wir erfassen:**\n"
            "• Persönliche Daten (Name, Geburtsdatum)\n"
            "• Kontaktinformationen (E-Mail, Telefon)\n"
            "• Adressdaten (Straße, PLZ, Stadt, Land)\n\n"
            "**Datenschutz:** Ihre Daten werden sicher gespeichert und nur für die Kontoverwaltung verwendet.\n\n"
            "**Sind Sie einverstanden mit diesem Registrierungsprozess?**\n"
            "Antworten Sie mit **'Ja'** um fortzufahren\n"
            "Antworten Sie mit **'Nein'** um abzubrechen"
        )

        await turn_context.send_activity(MessageFactory.text(welcome_message))
        # Transition to the next state
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CONSENT)

    async def _handle_consent_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input regarding consent
        user_input_lower = user_input.lower().strip()

        positive_responses = [
            'ja', 'yes', 'ok', 'okay', 'einverstanden', 'zustimmung',
            'zustimmen', 'akzeptieren', 'weiter', 'fortfahren', 'gerne',
            'si', 'oui', 'sí', '✓', '👍', 'y'
        ]


        negative_responses = [
            'nein', 'no', 'nicht einverstanden', 'ablehnen', 'abbrechen',
            'stop', 'halt', 'nee', 'nö', 'non', '✗', '👎', 'n'
        ]

        if any(response in user_input_lower for response in positive_responses):
            # User agrees - start registration
            confirmation_message = (
                "**Vielen Dank für Ihr Einverständnis!**\n\n"
                "Die Registrierung beginnt jetzt. Lassen Sie uns mit Ihrem Geschlecht beginnen."
            )
            await turn_context.send_activity(MessageFactory.text(confirmation_message))
            user_profile['consent_given'] = True
            user_profile['consent_timestamp'] = datetime.now().isoformat()
            await self.user_profile_accessor.set(turn_context, user_profile)
            # Proceed to ask for gender
            await self._ask_for_gender(turn_context)

        elif any(response in user_input_lower for response in negative_responses):
            # User doesnt agrees - end the registration
            decline_message = (
                "❌ **Registrierung abgebrochen**\n\n"
                "Ich verstehe, dass Sie nicht fortfahren möchten. "
                "Die Registrierung wurde beendet.\n\n"
                "Falls Sie Ihre Meinung ändern, können Sie jederzeit eine neue "
                "Konversation beginnen und 'Hallo' sagen.\n\n"
                "Haben Sie noch einen schönen Tag!"
            )
            await turn_context.send_activity(MessageFactory.text(decline_message))

            # End the dialogue and reset state, marking registration as cancelled
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
            await self.user_profile_accessor.set(turn_context, {
                'consent_given': False,
                'consent_timestamp': datetime.now().isoformat(),
                'registration_cancelled': True
            })

        else:
            # unclear anwser - ask again
            clarification_message = (
                " **Entschuldigung, das habe ich nicht verstanden.**\n\n"
                "Bitte antworten Sie klar mit:\n"
                "**'Ja'** - um mit der Registrierung fortzufahren\n"
                " **'Nein'** - um den Prozess abzubrechen\n\n"
                "**Sind Sie einverstanden mit dem Registrierungsprozess?**"
            )
            await turn_context.send_activity(MessageFactory.text(clarification_message))

    async def _ask_for_gender(self, turn_context: TurnContext):
        # Asks the user for their gender, providing options
        gender_message = (
            "Bitte wählen Sie Ihr Geschlecht:\n\n"
            "1 **Männlich**\n"
            "2 **Weiblich**\n"
            "3 **Divers**\n"
            "4 **Keine Angabe**\n\n"
            "Sie können die Nummer oder den Begriff eingeben."
        )
        await turn_context.send_activity(MessageFactory.text(gender_message))
        # Transition to the next state
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_GENDER)

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile, user_input):
        #  Processes the user's input for gender
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

            # if the user is correcting mode and wants to correct the answer
            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'gender', 'Geschlecht', gender_display):
                return

            # set valid value
            await self._confirm_field(turn_context, "Geschlecht", gender_display, DialogState.CONFIRM_PREFIX + "gender")
        else:
            # if it isnt correct, reprompt
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte wählen Sie eine gültige Option (1-4) oder geben Sie das Geschlecht direkt ein.")
            )

    async def _ask_for_title(self, turn_context: TurnContext):
       # Asks the user for their academic title
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
        # Processes the user's input for academic title
        valid_titles = [
            "Dr.", "Prof.", "Prof. Dr.", "Prof. Dr. Dr.", "Dipl.-Ing.",
            "Dr.-Ing.", "Dr. phil.", "Dr. jur.", "Dr. med.", "Mag.", "Lic.", "Ph.D."
        ]
        no_title_keywords = ["kein", "keiner", "nein", "keine", "-", "none", ""]

        user_input_strip_lower = user_input.strip().lower()

        if user_input_strip_lower in no_title_keywords:
            # Store empty string if no title
            user_profile['title'] = ''
            # Display text for no title
            user_profile['title_display'] = "Kein Titel"
            await self.user_profile_accessor.set(turn_context, user_profile)

            # Check and handle correction mode
            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'title', 'Titel', "Kein Titel"):
                return

            # if not set the value
            await self._confirm_field(turn_context, "Titel", "Kein Titel", DialogState.CONFIRM_PREFIX + "title")
        # Check for exact match with valid title
        elif user_input in valid_titles:
            user_profile['title'] = user_input
            user_profile['title_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            # Check and handle correction mode
            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'title', 'Titel', user_input):
                return

            await self._confirm_field(turn_context, "Titel", user_input, DialogState.CONFIRM_PREFIX + "title")
        else:
            # Invalid input
            await turn_context.send_activity(
                MessageFactory.text("Bitte wählen Sie einen gültigen Titel aus der Liste oder geben Sie 'kein' ein.")
            )

    async def _ask_for_first_name(self, turn_context: TurnContext):
        # Asks the user for their first name
        await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihren **Vornamen** ein:"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_FIRST_NAME)

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile, user_input):
        # validate user input
        if DataValidator.validate_name_part(user_input):
            user_profile['first_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            # check if correction mode is true
            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'first_name', 'Vorname', user_input):
                return

            # if not, set name
            await self._confirm_field(turn_context, "Vorname", user_input, DialogState.CONFIRM_PREFIX + "first_name")
        else:
            # if not valid raise a message
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte geben Sie einen gültigen Vornamen ein (mindestens 2 Zeichen, nur Buchstaben):")
            )

    async def _ask_for_last_name(self, turn_context: TurnContext):
        # Asks the user for their last name
        await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihren **Nachnamen** ein:"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_LAST_NAME)

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile, user_input):
        #  Processes the user's input for the last name
        if DataValidator.validate_name_part(user_input):
            user_profile['last_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            # Check and handle correction mode
            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'last_name', 'Nachname', user_input):
                return

            await self._confirm_field(turn_context, "Nachname", user_input, DialogState.CONFIRM_PREFIX + "last_name")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie einen gültigen Nachnamen ein (mindestens 2 Zeichen):")
            )

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        # Asks the user for their birthdate in  TT.MM.JJJJ format
        await turn_context.send_activity(
            MessageFactory.text(
                "Bitte geben Sie Ihr **Geburtsdatum** ein (Format: TT.MM.JJJJ):\n\nBeispiel: 15.03.1990")
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile, user_input):
         # Processes the user's input for birthdate
         # and validate them
        birthdate = DataValidator.validate_birthdate(user_input)
        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            # Check and handle correction mode
            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'birth_date', 'Geburtsdatum', user_input):
                return

            await self._confirm_field(turn_context, "Geburtsdatum", user_input,
                                      DialogState.CONFIRM_PREFIX + "birthdate")
        else:
            # Invalid input
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie ein gültiges Geburtsdatum im Format TT.MM.JJJJ ein:")
            )

    async def _ask_for_email(self, turn_context: TurnContext):
        # Asks the user for their email address
        await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihre **E-Mail-Adresse** ein:"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile, user_input):
       # Processes the user's input for the email address
       # check if the email is already in use
        if DataValidator.validate_email(user_input):
            # The prompt was cut off here. Assuming it continues with validation and state handling
            if not user_profile.get('correction_mode'):
                if await self.customer_service.email_exists_in_db(user_input.strip().lower()):
                    await turn_context.send_activity(MessageFactory.text(
                        "Diese E-Mail-Adresse ist bereits registriert. Bitte geben Sie eine andere E-Mail ein."))
                    return

            user_profile['email'] = user_input.strip().lower()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'email', 'E-Mail', user_input):
                return

            await self._confirm_field(turn_context, "E-Mail", user_input, DialogState.CONFIRM_PREFIX + "email")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige E-Mail-Adresse ein:")
            )

    async def _ask_for_phone(self, turn_context: TurnContext):
        # ask for the phone number
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
        # Processes the user's input for the phone number
        phone_number_obj = DataValidator.validate_phone(user_input)
        if phone_number_obj:
            user_profile['telephone'] = phone_number_obj.as_e164
            user_profile['telephone_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'telephone', 'Telefonnummer', user_input):
                return

            await self._confirm_field(turn_context, "Telefonnummer", user_input, DialogState.CONFIRM_PREFIX + "phone")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige deutsche Telefonnummer ein:")
            )

    async def _ask_for_street(self, turn_context: TurnContext):
       # Asks the user for their street name
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihre **Straße** ein (ohne Hausnummer):\n\nBeispiel: Musterstraße")
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_STREET)

    async def _handle_street_input(self, turn_context: TurnContext, user_profile, user_input):
       # Processes the user's input for the street name
        if len(user_input.strip()) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['street_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'street_name', 'Straße', user_input):
                return

            await self._confirm_field(turn_context, "Straße", user_input, DialogState.CONFIRM_PREFIX + "street")
        else:
            await turn_context.send_activity(
                MessageFactory.text(
                    "Bitte geben Sie eine gültige Straße ein (mindestens 3 Zeichen, nur Buchstaben und Leerzeichen):")
            )

    async def _ask_for_house_number(self, turn_context: TurnContext):
        # Asks the user for their house number
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

                if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                                'house_number', 'Hausnummer', str(house_number)):
                    return

                await self._confirm_field(turn_context, "Hausnummer", str(house_number),
                                          DialogState.CONFIRM_PREFIX + "house_number")
            else:
                raise ValueError()
        except ValueError:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige Hausnummer (positive Zahl) ein:")
            )

    async def _ask_for_house_addition(self, turn_context: TurnContext):
        # Processes the user's input for the house number
        await turn_context.send_activity(
            MessageFactory.text(
                "Haben Sie einen **Hausnummernzusatz**? (optional)\n\n"
                "Beispiele: a, b, 1/2, links\n\n"
                "Geben Sie den Zusatz ein oder **'kein'** für keinen Zusatz:"
            )
        )
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_ADDITION)

    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile, user_input):
        # Asks the user for their house number addition (optional)
        if user_input.lower() in ["kein", "keiner", "nein", "keine", "-", ""]:
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
        # Asks the user for their postal code
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihre **Postleitzahl** ein:\n\nBeispiel: 12345"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_POSTAL)

    async def _handle_postal_input(self, turn_context: TurnContext, user_profile, user_input):
        # Asks the user for their city
        if DataValidator.validate_postal_code(user_input):
            user_profile['postal_code'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'postal_code', 'Postleitzahl', user_input):
                return

            await self._confirm_field(turn_context, "Postleitzahl", user_input, DialogState.CONFIRM_PREFIX + "postal")
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte geben Sie eine gültige deutsche Postleitzahl (5 Ziffern) ein:")
            )

    async def _ask_for_city(self, turn_context: TurnContext):
        # asks the user of their city
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihren **Ort/Stadt** ein:\n\nBeispiel: Berlin"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CITY)

    async def _handle_city_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input for the city
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
        # Asks the user for their country
        await turn_context.send_activity(
            MessageFactory.text("Bitte geben Sie Ihr **Land** ein:\n\nBeispiel: Deutschland"))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_COUNTRY)

    async def _handle_country_input(self, turn_context: TurnContext, user_profile, user_input):
         # process the user input
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['country_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'country_name', 'Land', user_input):
                return

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
            "**Zusammenfassung Ihrer Angaben:**\n\n"
            f"**1. Geschlecht:** {user_profile.get('gender_display', 'Nicht angegeben')}\n"
            f"**2. Titel:** {title_text}\n"
            f"**3. Vorname:** {user_profile.get('first_name', 'Nicht angegeben')}\n"
            f"**4. Nachname:** {user_profile.get('last_name', 'Nicht angegeben')}\n"
            f"**5. Geburtsdatum:** {user_profile.get('birth_date_display', 'Nicht angegeben')}\n"
            f"**6. E-Mail:** {user_profile.get('email', 'Nicht angegeben')}\n"
            f"**7. Telefon:** {user_profile.get('telephone_display', 'Nicht angegeben')}\n"
            f"**8. Straße:** {user_profile.get('street_name', 'Nicht angegeben')}\n"
            f"**9. Hausnummer:** {user_profile.get('house_number', 'Nicht angegeben')}\n"
            f"**10. Hausnummernzusatz:** {user_profile.get('house_addition_display', 'Kein Zusatz')}\n"
            f"**11. PLZ:** {user_profile.get('postal_code', 'Nicht angegeben')}\n"
            f"**12. Ort:** {user_profile.get('city', 'Nicht angegeben')}\n"
            f"**13. Land:** {user_profile.get('country_name', 'Nicht angegeben')}\n\n"
            "**Sind alle Angaben korrekt?**\n"
            "• **'Ja'** - Konto erstellen\n"
            "• **'Nein'** - Daten korrigieren\n"
            "• **'Neustart'** - von vorne beginnen"
        )

        await turn_context.send_activity(MessageFactory.text(summary))
        await self.dialog_state_accessor.set(turn_context, DialogState.FINAL_CONFIRMATION)

    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """Behandelt die finale Bestätigung und speichert die Daten."""
        user_input_lower = user_input.lower().strip()

        # Positive Bestätigung
        positive_responses = ["ja", "j", "yes", "y", "richtig", "korrekt", "ok", "okay", "bestätigen"]

        # Negative Antworten (für Korrektur)
        negative_responses = ["nein", "n", "no", "falsch", "inkorrekt", "korrigieren", "ändern"]

        # Neustart-Keywords
        restart_responses = ["neustart", "restart", "nochmal", "von vorne", "neu beginnen"]

        if any(response in user_input_lower for response in positive_responses):
            # Daten speichern
            await turn_context.send_activity(MessageFactory.text("💾 **Speichere Ihre Daten...**"))

            success = await self._save_customer_data(user_profile)

            if success:
                success_message = (
                    "**Registrierung erfolgreich abgeschlossen!**\n\n"
                    "Ihre Daten wurden erfolgreich gespeichert\n"
                    "Ihr Kundenkonto wurde erstellt\n\n"
                    "Vielen Dank für Ihre Registrierung! 😊"
                )
                await turn_context.send_activity(MessageFactory.text(success_message))

                await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
                await self.user_profile_accessor.set(turn_context, {
                    'registration_completed': True,
                    'completion_timestamp': datetime.now().isoformat()
                })
            else:
                error_message = (
                    "❌ **Fehler beim Speichern**\n\n"
                    "Entschuldigung, beim Speichern ist ein Problem aufgetreten.\n"
                    "• **'Nochmal'** - erneut versuchen\n"
                    "• **'Neustart'** - von vorne beginnen"
                )
                await turn_context.send_activity(MessageFactory.text(error_message))
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)

        elif any(response in user_input_lower for response in negative_responses):
            # Benutzer möchte Daten korrigieren
            await self._start_correction_process(turn_context, user_profile)

        elif any(response in user_input_lower for response in restart_responses):
            # Komplett neu starten
            await self._handle_restart_request(turn_context)

        else:
            # Unklare Antwort
            clarification_message = (
                "**Bitte präzisieren Sie:**\n\n"
                "• **'Ja'** - alle Daten sind korrekt, Konto erstellen\n"
                "• **'Nein'** - ich möchte etwas korrigieren\n"
                "• **'Neustart'** - komplett von vorne beginnen"
            )
            await turn_context.send_activity(MessageFactory.text(clarification_message))

    async def _save_customer_data(self, user_profile: dict) -> bool:
        """
        Speichert die gesammelten Benutzerdaten über den CustomerService.
        Verarbeitet die Daten vor und delegiert die DB-Operationen an den Service.
        """
        try:
            # Datenbankoperationen an Service delegieren
            return await self.customer_service.store_data_db(user_profile.copy())

        except Exception as e:
            print(f"Fehler bei der Datenvorverarbeitung: {e}")
            return False

    async def _handle_error_state(self, turn_context: TurnContext, user_profile, user_input):
        """Behandelt Fehler-Zustände und bietet Recovery-Optionen."""
        user_input_lower = user_input.lower().strip()

        retry_keywords = ["nochmal", "retry", "wieder", "erneut", "versuchen"]
        restart_keywords = ["neustart", "restart", "von vorne", "neu beginnen"]

        if any(keyword in user_input_lower for keyword in retry_keywords):
            # Nochmal versuchen - zurück zur finalen Bestätigung
            await turn_context.send_activity(MessageFactory.text("🔄 **Versuche es nochmal...**"))
            await self._show_final_summary(turn_context)

        elif any(keyword in user_input_lower for keyword in restart_keywords):
            # Komplett neu starten
            await self._handle_restart_request(turn_context)

        else:
            # Hilfe anbieten
            error_help_message = (
                "❌ **Ein Fehler ist aufgetreten.**\n\n"
                "**Was möchten Sie tun?**\n"
                "• **'Nochmal'** - erneut versuchen zu speichern\n"
                "• **'Neustart'** - komplett von vorne beginnen\n"
                "• **'Zurück'** - zur Zusammenfassung zurückkehren"
            )
            await turn_context.send_activity(MessageFactory.text(error_help_message))

    # === HILFS-METHODEN FÜR BESSERE UX ===

    async def _show_correction_help(self, turn_context: TurnContext):
        """Zeigt erweiterte Hilfe für das Korrektur-System."""
        help_message = (
            "ℹ️ **Hilfe zum Korrektur-System:**\n\n"
            "**Eingabe-Möglichkeiten:**\n"
            "• **Nummer eingeben:** '6' für E-Mail korrigieren\n"
            "• **Feldname eingeben:** 'email' oder 'e-mail'\n"
            "• **Teilbegriff:** 'telefon', 'adresse', 'name'\n\n"
            "**Navigation:**\n"
            "• **'Zurück'** - zur Zusammenfassung\n"
            "• **'Neustart'** - alles von vorne\n"
            "• **'Hilfe'** - diese Hilfe anzeigen\n\n"
            "**Was möchten Sie korrigieren?**"
        )
        await turn_context.send_activity(MessageFactory.text(help_message))

    async def _validate_correction_context(self, turn_context: TurnContext, user_profile, target_field):
        """Validiert ob ein Feld korrigiert werden kann und gibt entsprechende Meldungen."""
        current_value = user_profile.get(target_field)

        if not current_value:
            missing_message = (
                f"⚠️ **Feld '{target_field}' ist noch nicht ausgefüllt.**\n\n"
                f"Sie können es jetzt eingeben:"
            )
            await turn_context.send_activity(MessageFactory.text(missing_message))
            return True

        # Zeige aktuellen Wert
        display_fields = {
            'gender': 'gender_display',
            'title': 'title_display',
            'birth_date': 'birth_date_display',
            'telephone': 'telephone_display',
            'house_number_addition': 'house_addition_display'
        }

        display_field = display_fields.get(target_field, target_field)
        current_display = user_profile.get(display_field, current_value)

        current_value_message = (
            f"**Aktueller Wert:** {current_display}\n\n"
            f"Bitte geben Sie den neuen Wert ein:"
        )
        await turn_context.send_activity(MessageFactory.text(current_value_message))
        return True