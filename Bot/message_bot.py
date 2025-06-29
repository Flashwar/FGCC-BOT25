import re

from datetime import datetime
from injector import inject

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext, ConversationState, UserState
from botbuilder.schema import ChannelAccount

from Bot.azure_service.luis_service import AzureCLUService
from FCCSemesterAufgabe.settings import isDocker
from .dialogstate import DialogState
from .validators import DataValidator
from .services import CustomerService
from .text_messages import BotMessages, FieldConfig


class RegistrationTextBot(ActivityHandler):
    # Initializes the RegistrationTextBot

    @inject
    def __init__(self, conversation_state: ConversationState, user_state: UserState, customer_service: CustomerService):
        self.customer_service = customer_service
        self.conversation_state = conversation_state
        self.user_state = user_state

        if isDocker:
            self.clu_service = None
        else:
            print("🔧 Versuche CLU Service zu initialisieren...")
            self.clu_service = AzureCLUService()

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
        await turn_context.send_activity(MessageFactory.text(BotMessages.CORRECTION_OPTIONS))
        await self.dialog_state_accessor.set(turn_context, "correction_selection")

    async def _handle_correction_selection(self, turn_context: TurnContext, user_profile, user_input):
        """Handles the user's selection of which field to correct"""
        user_input_lower = user_input.lower().strip()

        # Handle special commands like "back" or "restart"
        if user_input_lower in ["zurück", "back", "summary", "zusammenfassung"]:
            await self._show_final_summary(turn_context)
            return
        elif user_input_lower in ["neustart", "restart", "von vorne"]:
            await self._handle_restart_request(turn_context)
            return

        # Process the correction selection
        target_field = None
        selected_field = None

        for key, field in FieldConfig.CORRECTION_MAPPING.items():
            if key in user_input_lower:
                target_field = field
                selected_field = key
                break

        if target_field:
            # Get the corresponding dialog state
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

            # Send correction start message
            correction_message = BotMessages.correction_start(field_display)
            await turn_context.send_activity(MessageFactory.text(correction_message))

            # Set the dialogue state to the target field
            await self.dialog_state_accessor.set(turn_context, target_state)

            # Mark that the bot is in correction mode
            user_profile['correction_mode'] = True
            user_profile['correction_return_to'] = 'final_summary'
            await self.user_profile_accessor.set(turn_context, user_profile)

        else:
            # Not understood
            await turn_context.send_activity(MessageFactory.text(BotMessages.CORRECTION_NOT_UNDERSTOOD))

    async def _handle_restart_request(self, turn_context: TurnContext):
        # Handles requests to restart the entire registration process
        await turn_context.send_activity(MessageFactory.text(BotMessages.RESTART_MESSAGE))

        # Reset user profile and dialogue state to start fresh
        await self.user_profile_accessor.set(turn_context, {})
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

        # Start new registration
        await self._handle_greeting(turn_context, {})

    async def _extract_specific_entity(self, user_input: str, entity_type: str):
        #  Sends input to CLU and searches for a specific entity type

        if not self.clu_service:
            return None

        try:
            entities = await self.clu_service.get_entities(text=user_input)
            print(f"🔧 CLU Entities für {entity_type}: {entities}")

            for entity in entities:
                entity_name = entity.get('name', '')
                entity_text = entity.get('text', '')

                if entity_name == entity_type:
                    print(f"✅ {entity_type} gefunden: '{entity_text}'")
                    return entity_text

            print(f"❌ Keine {entity_type} Entity gefunden")
            return None

        except Exception as e:
            print(f"CLU {entity_type} Extraktion Fehler: {e}")
            return None

    async def _check_correction_mode_and_handle(self, turn_context: TurnContext, user_profile,
                                                field_name, field_display, new_value):
        # Method to handle post-input logic when in correction mode
        if user_profile.get('correction_mode'):
            # Correction completed - confirm and return to summary
            correction_message = BotMessages.correction_success(field_display, new_value)
            await turn_context.send_activity(MessageFactory.text(correction_message))

            # Exit correction mode
            user_profile['correction_mode'] = False
            await self.user_profile_accessor.set(turn_context, user_profile)

            # Return to summary
            await self._show_final_summary(turn_context)
            return True  # Indicate that correction mode was active and handled

        return False  # Indicate that normal mode should continue

    async def _handle_completed_state(self, turn_context: TurnContext, user_profile, user_input):
        # Handles messages received when the registration process is in a completed state
        user_input_lower = user_input.lower()

        if any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            # Check if the previous registration was cancelled
            if user_profile.get('registration_cancelled'):
                await turn_context.send_activity(MessageFactory.text(BotMessages.RESTART_NEW_REGISTRATION))

                # Reset and restart registration
                await self.user_profile_accessor.set(turn_context, {})
                await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
                await self._handle_greeting(turn_context, {})

            elif user_profile.get('consent_given') and not user_profile.get('registration_cancelled'):
                # Registration was successful
                await turn_context.send_activity(MessageFactory.text(BotMessages.ALREADY_REGISTERED))
        else:
            # Other inquiries after registration is completed
            if user_profile.get('registration_cancelled'):
                await turn_context.send_activity(MessageFactory.text(BotMessages.REGISTRATION_CANCELLED_HELP))
            else:
                await turn_context.send_activity(MessageFactory.text(BotMessages.ALREADY_COMPLETED_HELP))

    async def _handle_unknown_state(self, turn_context: TurnContext, user_profile, user_input):
        """Handles situations where the bot is in an unknown or unexpected dialogue state"""
        user_input_lower = user_input.lower()

        if any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            # User wants a restart
            await turn_context.send_activity(MessageFactory.text(BotMessages.UNKNOWN_STATE_RESTART))

            # Reset state and set to registration beginning
            await self.user_profile_accessor.set(turn_context, {})
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
            await self._handle_greeting(turn_context, {})
        else:
            # Unknown state + no restart keywords
            await turn_context.send_activity(MessageFactory.text(BotMessages.UNKNOWN_STATE_CONFUSION))
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
        await turn_context.send_activity(MessageFactory.text(BotMessages.WELCOME_MESSAGE))
        # Transition to the next state
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CONSENT)

    async def _handle_consent_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input regarding consent
        user_input_lower = user_input.lower().strip()

        if any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES):
            # User agrees - start registration
            await turn_context.send_activity(MessageFactory.text(BotMessages.CONSENT_GRANTED))
            user_profile['consent_given'] = True
            user_profile['consent_timestamp'] = datetime.now().isoformat()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._ask_for_gender(turn_context)

        elif any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES):
            # User doesn't agree - end the registration
            await turn_context.send_activity(MessageFactory.text(BotMessages.CONSENT_DENIED))
            await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
            await self.user_profile_accessor.set(turn_context, {
                'consent_given': False,
                'consent_timestamp': datetime.now().isoformat(),
                'registration_cancelled': True
            })
        else:
            # Unclear answer - ask again
            await turn_context.send_activity(MessageFactory.text(BotMessages.CONSENT_UNCLEAR))

    async def _ask_for_gender(self, turn_context: TurnContext):
        # Asks the user for their gender, providing options
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS["gender"]))
        # Transition to the next state
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_GENDER)

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile, user_input):
        #  Processes the user's input for gender
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
            await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['gender']))

    async def _ask_for_title(self, turn_context: TurnContext):
        # Asks the user for their academic title
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['title']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_TITLE)

    async def _handle_title_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input for academic title
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
            await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['title']))

    async def _ask_for_first_name(self, turn_context: TurnContext):
        # Asks the user for their first name
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['first_name']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_FIRST_NAME)

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile, user_input):
        # validate user name
        name_entity = await self._extract_specific_entity(user_input, 'Name')
        if name_entity and DataValidator.validate_name_part(name_entity):
            user_profile['first_name'] = name_entity.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'first_name', 'Vorname', name_entity):
                return

            await self._confirm_field(turn_context, "Vorname", name_entity, DialogState.CONFIRM_PREFIX + "first_name")
            return

        # Fallback: Try normal validation
        if DataValidator.validate_name_part(user_input):
            user_profile['first_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'first_name', 'Vorname', user_input):
                return

            await self._confirm_field(turn_context, "Vorname", user_input, DialogState.CONFIRM_PREFIX + "first_name")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['first_name']))

    async def _ask_for_last_name(self, turn_context: TurnContext):
        # Asks the user for their last name
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['last_name']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_LAST_NAME)

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile, user_input):
        #  Processes the user's input for the last name
        name_entity = await self._extract_specific_entity(user_input, 'Name')
        if name_entity and DataValidator.validate_name_part(name_entity):
            user_profile['last_name'] = name_entity.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'last_name', 'Nachname', name_entity):
                return

            await self._confirm_field(turn_context, "Nachname", name_entity, DialogState.CONFIRM_PREFIX + "last_name")
            return

        # Fallback: Try normal validation
        if DataValidator.validate_name_part(user_input):
            user_profile['last_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'last_name', 'Nachname', user_input):
                return

            await self._confirm_field(turn_context, "Nachname", user_input, DialogState.CONFIRM_PREFIX + "last_name")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['last_name']))

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        # Asks the user for their birthdate in  TT.MM.JJJJ format
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['birthdate']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input for birthdate
        # and validate them
        date_entity = await self._extract_specific_entity(user_input, 'DateOfBirth')
        if date_entity:
            birthdate = DataValidator.validate_birthdate(date_entity)
            if birthdate:
                user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
                user_profile['birth_date_display'] = date_entity
                await self.user_profile_accessor.set(turn_context, user_profile)

                if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                                'birth_date', 'Geburtsdatum', date_entity):
                    return

                await self._confirm_field(turn_context, "Geburtsdatum", date_entity,
                                          DialogState.CONFIRM_PREFIX + "birthdate")
                return

        # Fallback: Try normal validation
        birthdate = DataValidator.validate_birthdate(user_input)
        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'birth_date', 'Geburtsdatum', user_input):
                return

            await self._confirm_field(turn_context, "Geburtsdatum", user_input,
                                      DialogState.CONFIRM_PREFIX + "birthdate")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['birthdate']))

    async def _ask_for_email(self, turn_context: TurnContext):
        # Asks the user for their email address
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['email']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input for the email address
        # check if the email is already in use
        email_entity = await self._extract_specific_entity(user_input, 'email')
        if email_entity and DataValidator.validate_email(email_entity):
            if not user_profile.get('correction_mode'):
                if await self.customer_service.email_exists_in_db(email_entity.strip().lower()):
                    await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['email_exists']))
                    return

            user_profile['email'] = email_entity.strip().lower()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'email', 'E-Mail', email_entity):
                return

            await self._confirm_field(turn_context, "E-Mail", email_entity, DialogState.CONFIRM_PREFIX + "email")
            return

        # Fallback: Try normal validation
        if DataValidator.validate_email(user_input):
            if not user_profile.get('correction_mode'):
                if await self.customer_service.email_exists_in_db(user_input.strip().lower()):
                    await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['email_exists']))
                    return

            user_profile['email'] = user_input.strip().lower()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'email', 'E-Mail', user_input):
                return

            await self._confirm_field(turn_context, "E-Mail", user_input, DialogState.CONFIRM_PREFIX + "email")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['email']))

    async def _ask_for_phone(self, turn_context: TurnContext):
        # ask for the phone number
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['phone']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_PHONE)

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile, user_input):
        # Processes the user's input for the phone number
        phone_entity = await self._extract_specific_entity(user_input, 'PhoneNumber')
        if phone_entity:
            phone_number_obj = DataValidator.validate_phone(phone_entity)
            if phone_number_obj:
                user_profile['telephone'] = phone_number_obj.as_e164
                user_profile['telephone_display'] = phone_entity
                await self.user_profile_accessor.set(turn_context, user_profile)

                if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                                'telephone', 'Telefonnummer', phone_entity):
                    return

                await self._confirm_field(turn_context, "Telefonnummer", phone_entity,
                                          DialogState.CONFIRM_PREFIX + "phone")
                return

        # Fallback: Try normal validation
        phone_number_obj = DataValidator.validate_phone(user_input)
        if phone_number_obj:
            user_profile['telephone'] = phone_number_obj.as_e164
            user_profile['telephone_display'] = user_input
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'telephone', 'Telefonnummer', user_input):
                return

            await self._confirm_field(turn_context, "Telefonnummer", user_input, DialogState.CONFIRM_PREFIX + "phone")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['phone']))

    async def _ask_for_street(self, turn_context: TurnContext):
        # Asks the user for their street name
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['street']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_STREET)

    # MODIFIED METHOD: Street input with CLU first
    async def _handle_street_input(self, turn_context: TurnContext, user_profile, user_input):
        # First: Try CLU for StreetHousenumber entity
        street_entity = await self._extract_specific_entity(user_input, 'StreetHousenumber')
        if street_entity:
            # Remove numbers and common additions to get street name
            street_name = re.sub(r'\s*\d+[a-zA-Z]*\s*$', '', street_entity).strip()

            if len(street_name) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', street_name):
                user_profile['street_name'] = street_name

                # Also extract and save house number if not already set
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

                await self._confirm_field(turn_context, "Straße", street_name, DialogState.CONFIRM_PREFIX + "street")
                return

        # Fallback: Try normal validation
        if len(user_input.strip()) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['street_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'street_name', 'Straße', user_input):
                return

            await self._confirm_field(turn_context, "Straße", user_input, DialogState.CONFIRM_PREFIX + "street")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['street']))

    async def _ask_for_house_number(self, turn_context: TurnContext):
        # Asks the user for their house number
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['house_number']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_NUMBER)

    async def _handle_house_number_input(self, turn_context: TurnContext, user_profile, user_input):
        # First: Try CLU for StreetHousenumber entity (might contain house number)
        street_entity = await self._extract_specific_entity(user_input, 'houseNumber')
        if street_entity:
            # Try to extract house number from StreetHousenumber entity
            # Look for numbers in the entity text
            numbers = re.findall(r'\d+', street_entity)
            if numbers:
                try:
                    house_number = int(numbers[-1])  # Take the last number found
                    if house_number > 0:
                        user_profile['house_number'] = house_number
                        await self.user_profile_accessor.set(turn_context, user_profile)

                        if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                                        'house_number', 'Hausnummer',
                                                                        str(house_number)):
                            return

                        await self._confirm_field(turn_context, "Hausnummer", str(house_number),
                                                  DialogState.CONFIRM_PREFIX + "house_number")
                        return
                except ValueError:
                    pass

        # Fallback: Try normal validation
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
                return
            else:
                raise ValueError()
        except ValueError:
            # Error case
            await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['house_number']))

    async def _ask_for_house_addition(self, turn_context: TurnContext):
        # Processes the user's input for the house number
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['house_addition']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_ADDITION)

    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile, user_input):
        # Asks the user for their house number addition (optional)
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
        # Asks the user for their postal code
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['postal']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_POSTAL)

    async def _handle_postal_input(self, turn_context: TurnContext, user_profile, user_input):
        # Asks the user for their city
        zip_entity = await self._extract_specific_entity(user_input, 'ZipCode')
        if zip_entity:
            validated_postal = DataValidator.validate_postal_code(zip_entity)
            if validated_postal:
                user_profile['postal_code'] = validated_postal
                await self.user_profile_accessor.set(turn_context, user_profile)

                if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                                'postal_code', 'Postleitzahl', validated_postal):
                    return

                await self._confirm_field(turn_context, "Postleitzahl", validated_postal,
                                          DialogState.CONFIRM_PREFIX + "postal")
                return

        # Fallback: Try  validation
        validated_postal = DataValidator.validate_postal_code_enhanced(user_input)
        if validated_postal:
            user_profile['postal_code'] = validated_postal
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'postal_code', 'Postleitzahl', validated_postal):
                return

            await self._confirm_field(turn_context, "Postleitzahl", validated_postal,
                                      DialogState.CONFIRM_PREFIX + "postal")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['postal']))

    async def _ask_for_city(self, turn_context: TurnContext):
        # asks the user of their city
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['city']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CITY)

    async def _handle_city_input(self, turn_context: TurnContext, user_profile, user_input):
        # First: Try CLU for City entity
        city_entity = await self._extract_specific_entity(user_input, 'City')
        if city_entity and len(city_entity.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', city_entity.strip()):
            user_profile['city'] = city_entity.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'city', 'Ort', city_entity):
                return

            await self._confirm_field(turn_context, "Ort", city_entity, DialogState.CONFIRM_PREFIX + "city")
            return

        # Fallback: Try normal validation
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', user_input.strip()):
            user_profile['city'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'city', 'Ort', user_input):
                return

            await self._confirm_field(turn_context, "Ort", user_input, DialogState.CONFIRM_PREFIX + "city")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['city']))

    async def _ask_for_country(self, turn_context: TurnContext):
        # Asks the user for their country
        await turn_context.send_activity(MessageFactory.text(BotMessages.FIELD_PROMPTS['country']))
        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_COUNTRY)

    async def _handle_country_input(self, turn_context: TurnContext, user_profile, user_input):
        # First: Try CLU for countryName entity
        country_entity = await self._extract_specific_entity(user_input, 'countryName')
        if country_entity and len(country_entity.strip()) >= 2 and re.match(
                r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', country_entity.strip()):
            user_profile['country_name'] = country_entity.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'country_name', 'Land', country_entity):
                return

            await self._confirm_field(turn_context, "Land", country_entity, DialogState.CONFIRM_PREFIX + "country")
            return

        # Fallback: Try normal validation
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+', user_input.strip()):
            user_profile['country_name'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)

            if await self._check_correction_mode_and_handle(turn_context, user_profile,
                                                            'country_name', 'Land', user_input):
                return

            await self._confirm_field(turn_context, "Land", user_input, DialogState.CONFIRM_PREFIX + "country")
            return

        # Error case
        await turn_context.send_activity(MessageFactory.text(BotMessages.VALIDATION_ERRORS['country']))

    async def _confirm_field(self, turn_context: TurnContext, field_name: str, value: str, confirmation_state: str):
        # Sends a confirmation message for a field
        confirmation_message = BotMessages.confirmation_prompt(field_name, value)
        await turn_context.send_activity(MessageFactory.text(confirmation_message))
        await self.dialog_state_accessor.set(turn_context, confirmation_state)

    async def _handle_confirmation(self, turn_context: TurnContext, user_profile, user_input, dialog_state):
        """Handles confirmation requests and controls dialog flow based on 'yes'/'no'"""
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
                    await turn_context.send_activity(MessageFactory.text(BotMessages.CONFIRMATION_REJECTED))
                    await correction_ask_func(turn_context)
                    found_correction_step = True
                    break
            if not found_correction_step:
                await turn_context.send_activity(
                    MessageFactory.text("Entschuldigung, ich kann diesen Schritt nicht korrigieren."))
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        else:
            await turn_context.send_activity(MessageFactory.text(BotMessages.CONFIRMATION_UNCLEAR))

    async def _show_final_summary(self, turn_context: TurnContext):
        """Shows a summary of collected data and asks for final confirmation"""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        summary_message = BotMessages.final_summary(user_profile)
        await turn_context.send_activity(MessageFactory.text(summary_message))
        await self.dialog_state_accessor.set(turn_context, DialogState.FINAL_CONFIRMATION)

    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile, user_input):
        """Handles the final confirmation and saves the data"""
        user_input_lower = user_input.lower().strip()

        if any(response in user_input_lower for response in FieldConfig.POSITIVE_RESPONSES):
            # Save data
            await turn_context.send_activity(MessageFactory.text(BotMessages.SAVE_IN_PROGRESS))

            success = await self._save_customer_data(user_profile)

            if success:
                await turn_context.send_activity(MessageFactory.text(BotMessages.REGISTRATION_SUCCESS))
                await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
                await self.user_profile_accessor.set(turn_context, {
                    'registration_completed': True,
                    'completion_timestamp': datetime.now().isoformat()
                })
            else:
                await turn_context.send_activity(MessageFactory.text(BotMessages.SAVE_ERROR))
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)

        elif any(response in user_input_lower for response in FieldConfig.NEGATIVE_RESPONSES):
            # User wants to correct data
            await self._start_correction_process(turn_context, user_profile)

        elif any(response in user_input_lower for response in FieldConfig.RESTART_KEYWORDS):
            # Complete restart
            await self._handle_restart_request(turn_context)

        else:
            # Unclear answer
            await turn_context.send_activity(MessageFactory.text(BotMessages.FINAL_CONFIRMATION_UNCLEAR))

    async def _start_correction_process(self, turn_context: TurnContext, user_profile):
        """Starts the correction process by displaying a list of fields the user can choose to modify"""
        await turn_context.send_activity(MessageFactory.text(BotMessages.CORRECTION_OPTIONS))
        await self.dialog_state_accessor.set(turn_context, "correction_selection")

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
        """Handles error states and offers recovery options"""
        user_input_lower = user_input.lower().strip()

        retry_keywords = ["nochmal", "retry", "wieder", "erneut", "versuchen"]

        if any(keyword in user_input_lower for keyword in retry_keywords):
            # Try again - return to final confirmation
            await turn_context.send_activity(MessageFactory.text("🔄 **Versuche es nochmal...**"))
            await self._show_final_summary(turn_context)

        elif any(keyword in user_input_lower for keyword in FieldConfig.RESTART_KEYWORDS):
            # Complete restart
            await self._handle_restart_request(turn_context)

        else:
            # Offer help
            await turn_context.send_activity(MessageFactory.text(BotMessages.ERROR_HELP))

    async def _show_correction_help(self, turn_context: TurnContext):
        """Shows extended help for the correction system"""
        await turn_context.send_activity(MessageFactory.text(BotMessages.CORRECTION_HELP))
