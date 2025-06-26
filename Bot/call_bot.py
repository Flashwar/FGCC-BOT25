import sys
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

from botbuilder.core import (
    ActivityHandler,
    TurnContext,
    MessageFactory,
    ConversationState,
    UserState
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ChannelAccount,
    Attachment,
    SuggestedActions,
    CardAction,
    ActionTypes
)

# Django Imports für Validierung und DB
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers import NumberParseException, parse, is_valid_number
from asgiref.sync import sync_to_async

# Importiere deine bestehenden Services und Models
from azure_service.luis_service import AzureCLUService
from azure_service.speech_service import AzureSpeechService
from azure_service.keyvault import AzureKeyVaultService
from .models import Customer, AddressCountry, AddressStreet, AddressCity, Address, CustomerContact

class DialogState:
    """Dialog-Zustände für die Registrierung"""
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
    CONFIRM_PREFIX = "confirm_"


class CallState:
    """Call-spezifische Zustände"""
    IDLE = "idle"
    INCOMING = "incoming"
    ESTABLISHED = "established"
    WAITING_FOR_SPEECH = "waiting_for_speech" # Bot wartet auf Spracheingabe vom Benutzer
    PROCESSING_SPEECH = "processing_speech" # Bot verarbeitet Spracheingabe (STT, CLU)
    SPEAKING_RESPONSE = "speaking_response" # Bot spricht eine Antwort (TTS)
    CALL_ENDED = "call_ended"


class UnifiedTeamsBot(ActivityHandler):
    """
    Unified Teams Bot der sowohl Text-Chat als auch Telefon-Anrufe behandelt
    Verwendet Azure Speech Services und CLU für natürliche Sprachinteraktion
    """

    def __init__(self, conversation_state: ConversationState, user_state: UserState):
        super().__init__()

        # Zustandsmanagement
        self.conversation_state = conversation_state
        self.user_state = user_state

        # State Accessors
        self.user_profile_accessor = self.conversation_state.create_property("UserProfile")
        self.dialog_state_accessor = self.conversation_state.create_property("DialogState")
        self.call_state_accessor = self.conversation_state.create_property("CallState")
        self.call_info_accessor = self.conversation_state.create_property("CallInfo")

        # Azure Services initialisieren
        try:
            keyvault = AzureKeyVaultService()
            self.speech_service = AzureSpeechService(keyvault=keyvault)
            self.clu_service = AzureCLUService(keyvault=keyvault)
            print("✅ Azure Services erfolgreich initialisiert", file=sys.stdout)
        except Exception as e:
            print(f"⚠️ Azure Services nicht verfügbar: {e}", file=sys.stderr)
            self.speech_service = None
            self.clu_service = None

        # Dialog-Handler Mapping
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

        # Dialog Flow Definition
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

    # === BOT FRAMEWORK EVENT HANDLERS ===

    async def on_invoke_activity(self, turn_context: TurnContext) -> None:
        """
        Behandelt Teams Call Events (Invoke Activities).
        Diese Aktivitäten werden vom Bot Framework Connector gesendet,
        wenn Anruf-bezogene Ereignisse auftreten (z.B. eingehender Anruf, Anruf etabliert).
        """
        try:
            invoke_name = turn_context.activity.name
            invoke_value = turn_context.activity.value
            print(f"📞 Invoke Activity empfangen: {invoke_name}, Value: {invoke_value}", file=sys.stdout)

            # Beispielhafte Behandlung von Invoke Activities.
            # Die genaue Struktur der invoke_name hängt vom Typ des Call Events ab.
            if invoke_name == "calling/invite":
                await self._handle_call_invite(turn_context)
                # Antwort für "calling/invite" muss ein JSON mit "callbackUri" sein
                # und wird vom Adapter zurückgegeben.
                # Hier geben wir die notwendigen Informationen zurück, der Adapter wandelt es um.
                turn_context.activity.value = {
                    "callbackUri": self._get_callback_uri(),
                    "acceptModalityTypes": ["audio"], # Wir akzeptieren nur Audio
                    "mediaConfiguration": {
                        "removeFromDefaultAudioGroup": False # Bot soll Audio empfangen
                    }
                }
                turn_context.activity.value_type = "application/json" # Wichtig für die korrekte Antwort
                turn_context.activity.type = ActivityTypes.invoke_response # Indicate this is a response

            elif invoke_name == "calling/established":
                await self._handle_call_established(turn_context)
                # Standard 200 OK für etablierte Anrufe
                turn_context.activity.value = {"status": 200}
                turn_context.activity.value_type = "application/json"
                turn_context.activity.type = ActivityTypes.invoke_response

            elif invoke_name == "calling/terminated":
                await self._handle_call_terminated(turn_context)
                turn_context.activity.value = {"status": 200}
                turn_context.activity.value_type = "application/json"
                turn_context.activity.type = ActivityTypes.invoke_response

            elif "participants" in invoke_name.lower():
                await self._handle_participants_event(turn_context)
                turn_context.activity.value = {"status": 200}
                turn_context.activity.value_type = "application/json"
                turn_context.activity.type = ActivityTypes.invoke_response

            else:
                print(f"❓ Unbekannte Invoke Activity: {invoke_name}", file=sys.stdout)
                turn_context.activity.value = {"status": 400, "message": "Unknown Invoke Activity"}
                turn_context.activity.value_type = "application/json"
                turn_context.activity.type = ActivityTypes.invoke_response

        except Exception as e:
            print(f"❌ Fehler bei Invoke Activity: {e}", file=sys.stderr)
            # Im Fehlerfall auch eine Invoke Response senden
            turn_context.activity.value = {"status": 500, "message": f"Internal Server Error: {e}"}
            turn_context.activity.value_type = "application/json"
            turn_context.activity.type = ActivityTypes.invoke_response
            await self._handle_error(turn_context, str(e)) # Bot-internen Fehlerhandler aufrufen

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Behandelt eingehende Nachrichten (Text und Audio)"""
        try:
            # Bestimme, ob der Kontext ein Anruf ist oder ein Text-Chat
            is_call = self._is_call_context(turn_context)

            if is_call:
                await self._handle_call_message(turn_context)
            else:
                await self._handle_text_message(turn_context)

        except Exception as e:
            print(f"❌ Fehler bei Nachrichtenverarbeitung: {e}", file=sys.stderr)
            await self._handle_error(turn_context, str(e))

    async def on_members_added_activity(self, members_added: List[ChannelAccount], turn_context: TurnContext):
        """Behandelt neue Konversationsteilnehmer"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._initialize_conversation(turn_context)
                break
        await self.conversation_state.save_changes(turn_context) # Wichtig: Zustand speichern
        await self.user_state.save_changes(turn_context)

    async def _initialize_conversation(self, turn_context: TurnContext):
        """Initialisiert den Konversationszustand für neue Teilnehmer."""
        # Setzt den Dialogzustand auf GREETING
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
        # Setzt den Anrufzustand auf IDLE (falls nicht bereits geschehen)
        await self.call_state_accessor.set(turn_context, CallState.IDLE)
        # Leert das Benutzerprofil
        await self.user_profile_accessor.set(turn_context, {})
        # Ruft den Begrüßungshandler auf
        await self._handle_greeting(turn_context, {}) # user_profile ist am Anfang leer

    # === HELPER METHODS ===

    def _is_call_context(self, turn_context: TurnContext) -> bool:
        """
        Prüft, ob die aktuelle Aktivität im Kontext eines Sprachanrufs stattfindet.
        Im Service-hosted Media Modell sind dies typischerweise Aktivitäten vom Channel 'msteams'
        mit bestimmten Eigenschaften (z.B. Aktivitätstyp 'message' aber mit Audio-Anhang (wenn unterstützt),
        oder 'invoke' mit einem "calling"-Namen). Hier vereinfacht auf Channel-ID.
        """
        # Im Teams-Kanal sind Anrufe und Text-Chats oft beides 'msteams'.
        # Es ist komplex, hier 100%ig nur anhand der Activity zu unterscheiden,
        # da transkribierter Text als normale Nachricht kommt.
        # Ein robusterer Weg wäre, den CallState zu prüfen, der durch Invoke-Activities gesetzt wird.
        call_state = self.call_state_accessor.get(turn_context, lambda: CallState.IDLE)
        # Wenn der Bot in einem Anruf ist, behandeln wir Nachrichten als Teil des Anrufs.
        return turn_context.activity.channel_id == "msteams" and call_state != CallState.IDLE


    def _get_callback_uri(self) -> str:
        """
        Gibt die Callback-URI für den Calling Webhook zurück.
        Diese URL muss öffentlich erreichbar sein und im Azure Bot Service konfiguriert werden.
        """
        # Holen Sie die Basis-URL Ihres Django-Projekts / Bots.
        # Dies sollte eine Umgebungsvariable sein, z.B. YOUR_BOT_BASE_URL.
        # Beispiel: https://yourdomain.com/api/bot/calling
        callback_uri = os.environ.get("CALLING_WEBHOOK_URL")
        if not callback_uri:
            print("ERROR: CALLING_WEBHOOK_URL environment variable not set!", file=sys.stderr)
            # Im Entwicklungsmodus oder für lokale Tests könnte hier eine Dummy-URL stehen
            # aber für Produktion MUSS diese korrekt gesetzt sein.
            raise ValueError("CALLING_WEBHOOK_URL environment variable not set.")
        return callback_uri

    async def _handle_error(self, turn_context: TurnContext, error_message: str):
        """Standard-Fehlerbehandlung für Text- und Call-Kontext"""
        print(f"❌ Fehler aufgetreten: {error_message}", file=sys.stderr)
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        is_call = self._is_call_context(turn_context)

        response_message = "Entschuldigung, es ist ein unerwarteter Fehler aufgetreten. Bitte versuchen Sie es später erneut oder starten Sie den Dialog neu."
        if is_call:
            await self._speak_to_caller(turn_context, response_message)
        else:
            await turn_context.send_activity(MessageFactory.text(response_message))

        # Zustand auf Fehler setzen und Profil leeren für einen sauberen Neustart
        await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        await self.user_profile_accessor.set(turn_context, {})


    # === CALL HANDLING IMPLEMENTATION ===

    async def _handle_call_invite(self, turn_context: TurnContext):
        """Behandelt eingehende Anruf-Einladungen"""
        print(f"📞 Eingehender Anruf empfangen von: {turn_context.activity.from_property.id}", file=sys.stdout)
        await self.call_state_accessor.set(turn_context, CallState.INCOMING)

        # Speichere Call-Info (callId kommt im value der Activity)
        call_id = turn_context.activity.value.get("callId") if turn_context.activity.value else None
        caller_id = turn_context.activity.from_property.id if turn_context.activity.from_property else None

        call_info = {
            "call_id": call_id,
            "caller": caller_id,
            "start_time": datetime.now().isoformat()
        }
        await self.call_info_accessor.set(turn_context, call_info)

        print(f"📞 Anruf wird angenommen: {call_info}", file=sys.stdout)
        # Die Annahme erfolgt durch die Rückgabe der Invoke-Antwort in on_invoke_activity.

    async def _handle_call_established(self, turn_context: TurnContext):
        """Behandelt erfolgreich aufgebaute Anrufe"""
        print(f"📞 Anruf erfolgreich aufgebaut: {turn_context.activity.value.get('callId')}", file=sys.stdout)
        await self.call_state_accessor.set(turn_context, CallState.ESTABLISHED)

        # Initialisiere Dialog-State für neue Anrufe, falls nicht schon geschehen
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)
        if dialog_state == DialogState.GREETING:
            await self._start_call_registration(turn_context)
        else:
            # Wenn der Dialog bereits läuft, einfach den nächsten Schritt fortsetzen
            pass # Der Bot wartet auf Input, wenn der Call etabliert ist.


    async def _handle_call_terminated(self, turn_context: TurnContext):
        """Behandelt beendete Anrufe"""
        print(f"📞 Anruf beendet: {turn_context.activity.value.get('callId')}", file=sys.stdout)
        await self.call_state_accessor.set(turn_context, CallState.CALL_ENDED)

        # Optional: Speichere Gesprächsprotokoll
        call_info = await self.call_info_accessor.get(turn_context, lambda: {})
        call_info["end_time"] = datetime.now().isoformat()
        await self.call_info_accessor.set(turn_context, call_info)

        # Zustand für nächsten Anruf zurücksetzen
        await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
        await self.user_profile_accessor.set(turn_context, {})
        await self.call_info_accessor.set(turn_context, {})


    async def _handle_participants_event(self, turn_context: TurnContext):
        """Behandelt Teilnehmer-Events (z.B. Hinzufügen/Entfernen von Teilnehmern)"""
        print(f"👥 Teilnehmer-Event empfangen: {turn_context.activity.value}", file=sys.stdout)
        # Hier können Sie Logik hinzufügen, um auf Teilnehmeränderungen zu reagieren.


    async def _handle_call_message(self, turn_context: TurnContext):
        """
        Behandelt Nachrichten im Call-Kontext.
        Im Service-hosted Media Szenario enthält activity.text bereits die STT-Transkription.
        """
        call_state = await self.call_state_accessor.get(turn_context, lambda: CallState.IDLE)
        # Wenn der Anruf noch nicht etabliert ist oder beendet wurde, ignorieren.
        if call_state not in [CallState.ESTABLISHED, CallState.WAITING_FOR_SPEECH, CallState.PROCESSING_SPEECH]:
            print(f"DEBUG: Message in unexpected call state {call_state}, ignoring.", file=sys.stdout)
            return

        user_input_text = turn_context.activity.text
        if user_input_text:
            print(f"🎤 Erkannt (vom Teams STT): {user_input_text}", file=sys.stdout)
            await self._process_call_text(turn_context, user_input_text)
        else:
            # Fallback für den seltenen Fall, dass eine Nachricht im Anrufkontext kommt,
            # aber keinen Text enthält (z.B. nur ein Anhang).
            print("WARN: Call message received with no text.", file=sys.stderr)
            await self._speak_to_caller(turn_context,
                                        "Entschuldigung, ich konnte Sie nicht verstehen. Bitte sprechen Sie deutlich.")

    async def _process_call_text(self, turn_context: TurnContext, text: str):
        """Verarbeitet Text in einem Call (von STT oder direkter Input)"""
        await self.call_state_accessor.set(turn_context, CallState.PROCESSING_SPEECH)
        try:
            # CLU-Analyse für bessere Intent-Erkennung
            if self.clu_service:
                clu_result = await self.clu_service.analyze_conversation(text)
                intent_info = self._extract_intent_from_clu(clu_result)
                print(f"DEBUG: CLU Intent für '{text}': {intent_info['intent']}", file=sys.stdout)
            else:
                intent_info = self._extract_intent_simple(text)
                print(f"DEBUG: Simple Intent für '{text}': {intent_info['intent']}", file=sys.stdout)

            # Verarbeite mit Registrierungslogik
            await self._process_registration_input_call(turn_context, text, intent_info)

        except Exception as e:
            print(f"❌ Fehler bei Text-Verarbeitung im Call: {e}", file=sys.stderr)
            await self._speak_to_caller(turn_context, "Es ist ein Fehler bei der Verarbeitung Ihrer Eingabe aufgetreten. Bitte versuchen Sie es erneut.")

        finally:
            # Nach der Verarbeitung auf Warten auf Sprache zurücksetzen
            await self.call_state_accessor.set(turn_context, CallState.WAITING_FOR_SPEECH)

    async def _start_call_registration(self, turn_context: TurnContext):
        """Startet den Registrierungsprozess für einen Anruf"""
        welcome_text = (
            "Hallo! Willkommen bei unserem Kundenregistrierungsservice. "
            "Ich helfe Ihnen dabei, ein neues Kundenkonto zu erstellen. "
            "Dafür benötige ich einige persönliche Informationen von Ihnen. "
            "Lassen Sie uns beginnen!"
        )
        await self._speak_to_caller(turn_context, welcome_text)
        await self._ask_for_gender(turn_context) # Startet den Dialog an der ersten Frage


    async def _speak_to_caller(self, turn_context: TurnContext, text: str):
        """
        Spricht Text zum Anrufer (TTS).
        Im Service-hosted Media Modell sendet der Bot eine Textnachricht,
        die Teams dann in Sprache umwandelt und abspielt.
        Für komplexere Szenarien (z.B. Abspielen einer spezifischen Audiodatei)
        müsste die Microsoft Graph Calling API direkt genutzt werden (playPrompt).
        """
        await self.call_state_accessor.set(turn_context, CallState.SPEAKING_RESPONSE)
        try:
            if self.speech_service:
                # Hier würde man normalerweise die Text-to-Speech-Funktion aufrufen.
                # In einem Service-hosted Media Bot ist dies oft nicht nötig, da Teams es selbst macht.
                # Wenn Sie jedoch die Qualität des Azure Speech TTS nutzen wollen und Teams es erlaubt,
                # könnten Sie die Audio-Bytes hier erzeugen und dann an die Graph API senden.
                # Für diese korrigierte Version senden wir einfach den Text an Teams.
                # ABER: Die ursprüngliche Absicht war, audio_bytes zu erzeugen und zu senden.
                # Dies simuliere ich hier als Kommentar.
                # audio_bytes = self.speech_service.text_to_speech_bytes(text)
                # if audio_bytes:
                #    await self._send_audio_to_call(turn_context, audio_bytes) # Simuliert
                #    print(f"🔊 Spreche Audio (simuliert) für: {text[:50]}...", file=sys.stdout)
                # else:
                #    print(f"❌ TTS Service konnte Audio nicht generieren. Sende Text.", file=sys.stderr)
                #    await turn_context.send_activity(MessageFactory.text(text))

                # Standard für Service-Hosted Media: Sende einfach Text und Teams macht TTS.
                # Man könnte den Text noch mit SSML formatieren, um die Sprachausgabe zu steuern.
                await turn_context.send_activity(MessageFactory.text(text))
                print(f"🔊 Sende Text für Teams TTS: {text[:50]}...", file=sys.stdout)
            else:
                # Fallback, wenn Azure Speech Service nicht verfügbar ist
                print("WARN: Speech Service not available. Sending text fallback.", file=sys.stderr)
                await turn_context.send_activity(MessageFactory.text(text))

        except Exception as e:
            print(f"❌ Fehler beim Sprechen (TTS/Senden): {e}", file=sys.stderr)
            await turn_context.send_activity(MessageFactory.text("Entschuldigung, ich kann gerade nicht sprechen."))

        finally:
            await self.call_state_accessor.set(turn_context, CallState.WAITING_FOR_SPEECH)


    # === SIMULATED GRAPH API INTERACTION (for playPrompt) ===
    # WICHTIG: Dies ist eine vereinfachte Darstellung.
    # Eine echte Implementierung würde HTTP-Anfragen an die Microsoft Graph API erfordern,
    # Authentifizierung mit einem Access Token und die korrekte Handhabung von Graph API-Antworten.
    async def _send_audio_to_call(self, turn_context: TurnContext, audio_bytes: bytes):
        """
        Simuliert das Senden von Audio-Bytes an einen aktiven Teams-Anruf über die Graph API.
        Dies ist NICHT die vollständige Implementierung.
        Eine echte Implementierung würde beinhalten:
        1. Base64-Kodierung der audio_bytes oder Speichern in einem temporären, öffentlich zugänglichen Speicher.
        2. Erhalten eines Access Tokens für Microsoft Graph.
        3. Senden einer POST-Anfrage an
           `https://graph.microsoft.com/beta/communications/calls/{callId}/playPrompt`
           mit einem Body, der die Audioquelle angibt (z.B. eine MediaInfo mit `uri` oder `content`).
        """
        call_info = await self.call_info_accessor.get(turn_context, lambda: {})
        call_id = call_info.get("call_id")

        if not call_id:
            print("ERROR: Cannot send audio to call: No call ID found.", file=sys.stderr)
            return

        print(f"Simuliere Senden von {len(audio_bytes)} Bytes Audio an Call {call_id}...", file=sys.stdout)
        # Hier würde der tatsächliche HTTP-Aufruf zur Graph API erfolgen.
        # Beispiel (pseudo-code):
        # graph_url = f"https://graph.microsoft.com/beta/communications/calls/{call_id}/playPrompt"
        # headers = {"Authorization": "Bearer YOUR_GRAPH_ACCESS_TOKEN", "Content-Type": "application/json"}
        # payload = {
        #     "prompts": [
        #         {"@odata.type": "#microsoft.graph.mediaPrompt", "mediaInfo": {"uri": "data:audio/wav;base64,...", "resourceId": str(uuid.uuid4())}}
        #         # Oder eine URL zu einer MP3-Datei: {"@odata.type": "#microsoft.graph.mediaPrompt", "mediaInfo": {"uri": "https://yourcdn.com/audio.mp3", "resourceId": str(uuid.uuid4())}}
        #     ]
        # }
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(graph_url, headers=headers, json=payload) as response:
        #         response.raise_for_status()
        #         print(f"Graph playPrompt response: {await response.json()}", file=sys.stdout)


    # === TEXT CHAT HANDLING IMPLEMENTATION ===

    async def _handle_text_message(self, turn_context: TurnContext):
        """Behandelt reguläre Text-Nachrichten"""
        user_input = turn_context.activity.text.strip()
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

        # CLU-Analyse
        if self.clu_service:
            clu_result = await self.clu_service.analyze_conversation(user_input)
            intent_info = self._extract_intent_from_clu(clu_result)
        else:
            intent_info = self._extract_intent_simple(user_input)

        # Spezielle Intent-Behandlung für Text-Chat
        if intent_info['intent'] == 'Greeting':
            await self._handle_greeting_intent(turn_context)
        elif intent_info['intent'] == 'Help':
            await self._handle_help_intent(turn_context)
        elif intent_info['intent'] == 'EndConversation':
            await self._handle_goodbye_intent(turn_context)
        else:
            # Standard-Registrierungslogik für Text-Chat
            await self._process_registration_input_text(turn_context, user_input, intent_info)


    async def _process_registration_input_text(self, turn_context: TurnContext, user_input: str, intent_info: Dict):
        """Verarbeitet Registrierungseingaben für Text-Chat"""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

        # Bestätigungslogik
        if dialog_state.startswith(DialogState.CONFIRM_PREFIX):
            await self._handle_confirmation(turn_context, user_profile, user_input, dialog_state)
        elif dialog_state in self.dialog_handlers:
            await self.dialog_handlers[dialog_state](turn_context, user_profile, user_input)
        else:
            await turn_context.send_activity(MessageFactory.text(
                "Entschuldigung, ich bin verwirrt. Bitte starten Sie neu, indem Sie 'Hallo' sagen."))
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)

    async def _process_registration_input_call(self, turn_context: TurnContext, user_input: str, intent_info: Dict):
        """Verarbeitet Registrierungseingaben für Anrufe"""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})
        dialog_state = await self.dialog_state_accessor.get(turn_context, lambda: DialogState.GREETING)

        # Bestätigungslogik für Anrufe
        if dialog_state.startswith(DialogState.CONFIRM_PREFIX):
            await self._handle_confirmation_call(turn_context, user_profile, user_input, dialog_state)
        elif dialog_state in self.dialog_handlers:
            # Modifizierte Handler für Anrufe (verwenden _speak_to_caller)
            # Rufen Sie den spezifischen Handler auf und übergeben Sie alle benötigten Argumente
            await self.dialog_handlers[dialog_state](turn_context, user_profile, user_input)
        else:
            await self._speak_to_caller(turn_context,
                                        "Entschuldigung, ich bin verwirrt. Lassen Sie uns von vorne beginnen.")
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING)
            await self._ask_for_gender(turn_context) # Startet den Dialog neu

    # === DIALOG STATE HANDLERS (Angepasst für Sprachausgabe) ===

    async def _handle_greeting(self, turn_context: TurnContext, user_profile: Dict, user_input: str = None):
        """Behandelt Begrüßung"""
        welcome_message_text = (
            "Hallo! Willkommen bei unserem Kundenregistrierungsbot."
            "Ich helfe Ihnen dabei, ein neues Kundenkonto zu erstellen. "
            "Dafür benötige ich einige persönliche Informationen von Ihnen. "
            "Lassen Sie uns beginnen!"
        )

        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, welcome_message_text)
        else:
            await turn_context.send_activity(MessageFactory.text(welcome_message_text))

        await self._ask_for_gender(turn_context)

    async def _ask_for_gender(self, turn_context: TurnContext):
        """Fragt nach dem Geschlecht"""
        gender_message_chat = (
            "Bitte wählen Sie Ihr Geschlecht:\n\n"
            "1 Männlich\n"
            "2 Weiblich\n"
            "3 Divers\n"
            "4 Keine Angabe\n\n"
            "Sie können die Nummer oder den Begriff sagen."
        )
        gender_message_call = (
            "Bitte wählen Sie Ihr Geschlecht. "
            "Sagen Sie Männlich, Weiblich, Divers oder Keine Angabe."
        )

        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, gender_message_call)
        else:
            await turn_context.send_activity(MessageFactory.text(gender_message_chat))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_GENDER)

    async def _handle_gender_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Geschlecht-Eingabe"""
        gender_map = {
            "1": ("male", "Männlich"), "männlich": ("male", "Männlich"), "male": ("male", "Männlich"),
            "2": ("female", "Weiblich"), "weiblich": ("female", "Weiblich"), "female": ("female", "Weiblich"),
            "3": ("diverse", "Divers"), "divers": ("diverse", "Divers"), "diverse": ("diverse", "Divers"),
            "4": ("unspecified", "Keine Angabe"), "keine angabe": ("unspecified", "Keine Angabe"),
            "unspecified": ("unspecified", "Keine Angabe"),
        }

        user_input_lower = user_input.lower().strip()
        if user_input_lower in gender_map:
            gender_value, gender_display = gender_map[user_input_lower]
            user_profile['gender'] = gender_value
            user_profile['gender_display'] = gender_display
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Geschlecht", gender_display, DialogState.CONFIRM_PREFIX + "gender")
        else:
            error_msg = "Bitte wählen Sie eine gültige Option: Männlich, Weiblich, Divers oder Keine Angabe."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_title(self, turn_context: TurnContext):
        """Fragt nach dem Titel"""
        if self._is_call_context(turn_context):
            title_message = (
                "Haben Sie einen akademischen Titel? "
                "Sagen Sie zum Beispiel Doktor, Professor, oder sagen Sie 'kein' für keinen Titel."
            )
            await self._speak_to_caller(turn_context, title_message)
        else:
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

    async def _handle_title_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Titel-Eingabe"""
        valid_titles = [
            "Dr.", "Prof.", "Prof. Dr.", "Prof. Dr. Dr.", "Dipl.-Ing.",
            "Dr.-Ing.", "Dr. phil.", "Dr. jur.", "Dr. med.", "Mag.", "Lic.", "Ph.D.",
        ]
        valid_titles_lower = [t.lower().replace(".", "") for t in valid_titles] # für gesprochene Titel
        no_title_keywords = ["kein", "keiner", "nein", "keine", "-", "none", ""]

        user_input_clean = user_input.strip()
        user_input_lower = user_input_clean.lower()

        normalized_title = ""
        display_title = ""

        if user_input_lower in no_title_keywords:
            normalized_title = ''
            display_title = "Kein Titel"
        elif user_input_clean in valid_titles: # Exakte Übereinstimmung
            normalized_title = user_input_clean
            display_title = user_input_clean
        elif user_input_lower in valid_titles_lower: # Gesprochene Übereinstimmung
            # Versuche, den originalen Titel wiederherzustellen
            try:
                idx = valid_titles_lower.index(user_input_lower)
                normalized_title = valid_titles[idx]
                display_title = valid_titles[idx]
            except ValueError:
                # Fallback, falls nicht gefunden, aber sollte nicht passieren
                normalized_title = user_input_clean.title()
                display_title = user_input_clean.title()
        else:
            error_msg = "Bitte nennen Sie einen gültigen Titel oder sagen Sie 'kein'."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))
            return # Wichtig: Hier abbrechen, wenn Eingabe ungültig

        user_profile['title'] = normalized_title
        user_profile['title_display'] = display_title
        await self.user_profile_accessor.set(turn_context, user_profile)
        await self._confirm_field(turn_context, "Titel", display_title, DialogState.CONFIRM_PREFIX + "title")


    async def _ask_for_first_name(self, turn_context: TurnContext):
        """Fragt nach dem Vornamen"""
        message_call = "Bitte nennen Sie Ihren Vornamen."
        message_chat = "Bitte geben Sie Ihren **Vornamen** ein:"

        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, message_call)
        else:
            await turn_context.send_activity(MessageFactory.text(message_chat))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_FIRST_NAME)

    async def _handle_first_name_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Vorname-Eingabe"""
        if self._validate_name_part(user_input):
            user_profile['first_name'] = user_input.strip().title()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Vorname", user_input.strip().title(),
                                      DialogState.CONFIRM_PREFIX + "first_name")
        else:
            error_msg = "Bitte nennen Sie einen gültigen Vornamen mit mindestens 2 Buchstaben."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_last_name(self, turn_context: TurnContext):
        """Fragt nach dem Nachnamen"""
        message_call = "Bitte nennen Sie Ihren Nachnamen."
        message_chat = "Bitte geben Sie Ihren **Nachnamen** ein:"

        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, message_call)
        else:
            await turn_context.send_activity(MessageFactory.text(message_chat))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_LAST_NAME)

    async def _handle_last_name_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Nachname-Eingabe"""
        if self._validate_name_part(user_input):
            user_profile['last_name'] = user_input.strip().title()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Nachname", user_input.strip().title(),
                                      DialogState.CONFIRM_PREFIX + "last_name")
        else:
            error_msg = "Bitte nennen Sie einen gültigen Nachnamen mit mindestens 2 Buchstaben."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_birthdate(self, turn_context: TurnContext):
        """Fragt nach dem Geburtsdatum"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihr Geburtsdatum. Zum Beispiel: fünfzehnter März neunzehnhundertneunzig."
            await self._speak_to_caller(turn_context, message)
        else:
            message = "Bitte geben Sie Ihr **Geburtsdatum** ein (Format: TT.MM.JJJJ):\n\nBeispiel: 15.03.1990"
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_BIRTHDATE)

    async def _handle_birthdate_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Geburtsdatum-Eingabe"""
        birthdate = self._parse_birthdate(user_input)

        if birthdate:
            user_profile['birth_date'] = birthdate.strftime('%Y-%m-%d')
            user_profile['birth_date_display'] = birthdate.strftime('%d.%m.%Y')
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Geburtsdatum", user_profile['birth_date_display'],
                                      DialogState.CONFIRM_PREFIX + "birthdate")
        else:
            error_msg = "Bitte nennen Sie ein gültiges Geburtsdatum. Zum Beispiel: fünfzehnter März neunzehnhundertneunzig."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(
                    MessageFactory.text("Bitte geben Sie ein gültiges Geburtsdatum im Format TT.MM.JJJJ ein."))

    async def _ask_for_email(self, turn_context: TurnContext):
        """Fragt nach der E-Mail"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihre E-Mail-Adresse."
            await self._speak_to_caller(turn_context, message)
        else:
            await turn_context.send_activity(MessageFactory.text("Bitte geben Sie Ihre **E-Mail-Adresse** ein:"))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_EMAIL)

    async def _handle_email_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet E-Mail-Eingabe"""
        email = self._normalize_spoken_email(user_input)

        if self._validate_email(email):
            if await self._email_exists_in_db(email.lower()):
                error_msg = "Diese E-Mail-Adresse ist bereits registriert. Bitte nennen Sie eine andere E-Mail."
                if self._is_call_context(turn_context):
                    await self._speak_to_caller(turn_context, error_msg)
                else:
                    await turn_context.send_activity(MessageFactory.text(
                        "Diese E-Mail-Adresse ist bereits registriert. Bitte geben Sie eine andere E-Mail ein."))
                return

            user_profile['email'] = email.lower()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "E-Mail", email, DialogState.CONFIRM_PREFIX + "email")
        else:
            error_msg = "Bitte nennen Sie eine gültige E-Mail-Adresse."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(
                    MessageFactory.text("Bitte geben Sie eine gültige E-Mail-Adresse ein."))

    async def _ask_for_phone(self, turn_context: TurnContext):
        """Fragt nach der Telefonnummer"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihre Telefonnummer."
            await self._speak_to_caller(turn_context, message)
        else:
            message = (
                "Bitte geben Sie Ihre **Telefonnummer** ein:\n\n"
                "Beispiele:\n"
                "• +49 30 12345678\n"
                "• 030 12345678\n"
                "• 0175 1234567"
            )
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_PHONE)

    async def _handle_phone_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Telefonnummer-Eingabe"""
        phone_normalized = self._normalize_spoken_phone(user_input)
        phone_number_obj = self._validate_phone(phone_normalized)

        if phone_number_obj:
            user_profile['telephone'] = phone_number_obj.as_e164
            user_profile['telephone_display'] = phone_normalized
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Telefonnummer", phone_normalized,
                                      DialogState.CONFIRM_PREFIX + "phone")
        else:
            error_msg = "Bitte nennen Sie eine gültige deutsche Telefonnummer."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(
                    MessageFactory.text("Bitte geben Sie eine gültige deutsche Telefonnummer ein."))

    async def _ask_for_street(self, turn_context: TurnContext):
        """Fragt nach der Straße"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihre Straße, ohne Hausnummer."
            await self._speak_to_caller(turn_context, message)
        else:
            message = "Bitte geben Sie Ihre **Straße** ein (ohne Hausnummer):\n\nBeispiel: Musterstraße"
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_STREET)

    async def _handle_street_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Straße-Eingabe"""
        if len(user_input.strip()) >= 3 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['street_name'] = user_input.strip().title()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Straße", user_input.strip().title(),
                                      DialogState.CONFIRM_PREFIX + "street")
        else:
            error_msg = "Bitte nennen Sie eine gültige Straße (mindestens 3 Zeichen, nur Buchstaben und Leerzeichen)."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_house_number(self, turn_context: TurnContext):
        """Fragt nach der Hausnummer"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihre Hausnummer."
            await self._speak_to_caller(turn_context, message)
        else:
            message = "Bitte geben Sie Ihre **Hausnummer** ein:\n\nBeispiel: 42"
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_NUMBER)

    async def _handle_house_number_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Hausnummer-Eingabe"""
        try:
            house_number = int(user_input.strip())
            if house_number > 0:
                user_profile['house_number'] = house_number
                await self.user_profile_accessor.set(turn_context, user_profile)
                await self._confirm_field(turn_context, "Hausnummer", str(house_number),
                                          DialogState.CONFIRM_PREFIX + "house_number")
            else:
                raise ValueError("Hausnummer muss positiv sein.")
        except ValueError:
            error_msg = "Bitte nennen Sie eine gültige Hausnummer (positive Zahl)."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_house_addition(self, turn_context: TurnContext):
        """Fragt nach dem Hausnummernzusatz"""
        if self._is_call_context(turn_context):
            message = (
                "Haben Sie einen Hausnummernzusatz? Zum Beispiel A, B, oder 'kein' für keinen Zusatz."
            )
            await self._speak_to_caller(turn_context, message)
        else:
            message = (
                "Haben Sie einen **Hausnummernzusatz**? (optional)\n\n"
                "Beispiele: a, b, 1/2, links\n\n"
                "Geben Sie den Zusatz ein oder **'kein'** für keinen Zusatz:"
            )
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_HOUSE_ADDITION)

    async def _handle_house_addition_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Hausnummernzusatz-Eingabe"""
        no_addition_keywords = ["kein", "keiner", "nein", "keine", "-", "none", ""]
        user_input_lower = user_input.strip().lower()

        if user_input_lower in no_addition_keywords:
            user_profile['house_number_addition'] = ""
            user_profile['house_addition_display'] = "Kein Zusatz"
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Hausnummernzusatz", "Kein Zusatz",
                                      DialogState.CONFIRM_PREFIX + "house_addition")
        else:
            user_profile['house_number_addition'] = user_input.strip()
            user_profile['house_addition_display'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Hausnummernzusatz", user_input.strip(),
                                      DialogState.CONFIRM_PREFIX + "house_addition")

    async def _ask_for_postal(self, turn_context: TurnContext):
        """Fragt nach der Postleitzahl"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihre fünfstellige Postleitzahl."
            await self._speak_to_caller(turn_context, message)
        else:
            message = "Bitte geben Sie Ihre **Postleitzahl** ein:\n\nBeispiel: 12345"
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_POSTAL)

    async def _handle_postal_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Postleitzahl-Eingabe"""
        if self._validate_postal_code(user_input):
            user_profile['postal_code'] = user_input.strip()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Postleitzahl", user_input.strip(),
                                      DialogState.CONFIRM_PREFIX + "postal")
        else:
            error_msg = "Bitte nennen Sie eine gültige deutsche Postleitzahl (5 Ziffern)."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_city(self, turn_context: TurnContext):
        """Fragt nach dem Ort/Stadt"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihren Ort oder Ihre Stadt."
            await self._speak_to_caller(turn_context, message)
        else:
            message = "Bitte geben Sie Ihren **Ort/Stadt** ein:\n\nBeispiel: Berlin"
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_CITY)

    async def _handle_city_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Ort/Stadt-Eingabe"""
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['city'] = user_input.strip().title()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Ort", user_input.strip().title(), DialogState.CONFIRM_PREFIX + "city")
        else:
            error_msg = "Bitte nennen Sie einen gültigen Ort (mindestens 2 Zeichen, nur Buchstaben und Leerzeichen)."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _ask_for_country(self, turn_context: TurnContext):
        """Fragt nach dem Land"""
        if self._is_call_context(turn_context):
            message = "Bitte nennen Sie Ihr Land."
            await self._speak_to_caller(turn_context, message)
        else:
            message = "Bitte geben Sie Ihr **Land** ein:\n\nBeispiel: Deutschland"
            await turn_context.send_activity(MessageFactory.text(message))

        await self.dialog_state_accessor.set(turn_context, DialogState.ASK_COUNTRY)

    async def _handle_country_input(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Verarbeitet Land-Eingabe"""
        if len(user_input.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\.]+$', user_input.strip()):
            user_profile['country_name'] = user_input.strip().title()
            await self.user_profile_accessor.set(turn_context, user_profile)
            await self._confirm_field(turn_context, "Land", user_input.strip().title(), DialogState.CONFIRM_PREFIX + "country")
        else:
            error_msg = "Bitte nennen Sie ein gültiges Land (mindestens 2 Zeichen, nur Buchstaben und Leerzeichen)."
            if self._is_call_context(turn_context):
                await self._speak_to_caller(turn_context, error_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(error_msg))

    async def _confirm_field(self, turn_context: TurnContext, field_name: str, value: str, confirmation_state: str):
        """Sendet eine Bestätigungsnachricht für ein Feld."""
        confirmation_msg = f"{field_name}: **{value}**\n\nIst das korrekt? (ja/nein)"
        confirmation_msg_call = f"{field_name}: {value}. Ist das korrekt? Sagen Sie Ja oder Nein."

        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, confirmation_msg_call)
        else:
            await turn_context.send_activity(MessageFactory.text(confirmation_msg))
            # Optional: Suggested Actions für Text-Chat
            await turn_context.send_activity(
                MessageFactory.suggested_actions(
                    SuggestedActions(
                        actions=[
                            CardAction(
                                title="Ja",
                                type=ActionTypes.im_back,
                                value="Ja"
                            ),
                            CardAction(
                                title="Nein",
                                type=ActionTypes.im_back,
                                value="Nein"
                            )
                        ]
                    )
                )
            )
        await self.dialog_state_accessor.set(turn_context, confirmation_state)


    async def _handle_confirmation(self, turn_context: TurnContext, user_profile: Dict, user_input: str, dialog_state: str):
        """
        Behandelt Bestätigungsanfragen für TEXT-CHAT und steuert den Dialogfluss basierend auf 'ja'/'nein'.
        """
        user_input_lower = user_input.lower().strip()
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
                    MessageFactory.text("Entschuldigung, ich kann diesen Schritt nicht korrigieren. Bitte starten Sie neu.")
                )
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        else:
            await turn_context.send_activity(
                MessageFactory.text("Bitte antworten Sie mit 'ja' oder 'nein'.")
            )

    async def _handle_confirmation_call(self, turn_context: TurnContext, user_profile: Dict, user_input: str, dialog_state: str):
        """
        Behandelt Bestätigungsanfragen für SPRACAHANRUF und steuert den Dialogfluss basierend auf 'ja'/'nein'.
        """
        user_input_lower = user_input.lower().strip()
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
                await self._show_final_summary(turn_context) # Leitet zur finalen Bestätigung weiter
        elif rejected:
            found_correction_step = False
            for conf_state, _, correction_ask_func in self.dialog_flow:
                if dialog_state == conf_state:
                    await self._speak_to_caller(turn_context, "Okay, lassen Sie uns das korrigieren.")
                    await correction_ask_func(turn_context)
                    found_correction_step = True
                    break
            if not found_correction_step:
                await self._speak_to_caller(turn_context,
                    "Entschuldigung, ich kann diesen Schritt nicht korrigieren. Bitte versuchen Sie es erneut."
                )
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        else:
            await self._speak_to_caller(turn_context, "Bitte antworten Sie mit 'ja' oder 'nein'.")


    async def _show_final_summary(self, turn_context: TurnContext):
        """Zeigt eine Zusammenfassung der gesammelten Daten an und bittet um finale Bestätigung."""
        user_profile = await self.user_profile_accessor.get(turn_context, lambda: {})

        title_text = user_profile.get('title_display', 'Nicht angegeben') if user_profile.get('title_display') else 'Kein Titel'
        name_text = f"{user_profile.get('first_name', 'Nicht angegeben')} {user_profile.get('last_name', 'Nicht angegeben')}"

        address_parts = [user_profile.get('street_name', '')]
        if user_profile.get('house_number'):
            address_parts.append(str(user_profile['house_number']))
        if user_profile.get('house_number_addition'):
            address_parts.append(user_profile['house_number_addition'])
        address_text = " ".join(filter(None, address_parts)) if any(address_parts) else "Nicht angegeben"

        summary_template = (
            "Zusammenfassung Ihrer Angaben:\n\n"
            "Geschlecht: {gender_display}\n"
            "Titel: {title_text}\n"
            "Name: {name_text}\n"
            "Geburtsdatum: {birth_date_display}\n"
            "E-Mail: {email}\n"
            "Telefon: {telephone_display}\n"
            "Adresse: {address_text}\n"
            "PLZ/Ort: {postal_code} {city}\n"
            "Land: {country_name}\n\n"
            "Sind alle Angaben korrekt und soll ich das Konto erstellen? (ja/nein)"
        )

        summary_filled = summary_template.format(
            gender_display=user_profile.get('gender_display', 'Nicht angegeben'),
            title_text=title_text,
            name_text=name_text,
            birth_date_display=user_profile.get('birth_date_display', 'Nicht angegeben'),
            email=user_profile.get('email', 'Nicht angegeben'),
            telephone_display=user_profile.get('telephone_display', 'Nicht angegeben'),
            address_text=address_text,
            postal_code=user_profile.get('postal_code', 'Nicht angegeben'),
            city=user_profile.get('city', 'Nicht angegeben'),
            country_name=user_profile.get('country_name', 'Nicht angegeben')
        )

        if self._is_call_context(turn_context):
            # Für Anrufe eine prägnantere Zusammenfassung oder gezielte Abfrage
            call_summary_text = (
                f"Ihre Angaben sind: Geschlecht {user_profile.get('gender_display', 'Nicht angegeben')}, "
                f"Name {name_text}, Geburtsdatum {user_profile.get('birth_date_display', 'Nicht angegeben')}, "
                f"E-Mail {user_profile.get('email', 'Nicht angegeben')}, "
                f"Telefon {user_profile.get('telephone_display', 'Nicht angegeben')}, "
                f"Adresse {address_text}, "
                f"Postleitzahl {user_profile.get('postal_code', 'Nicht angegeben')} und Ort {user_profile.get('city', 'Nicht angegeben')}, "
                f"Land {user_profile.get('country_name', 'Nicht angegeben')}. "
                "Sind alle Angaben korrekt und soll ich das Konto erstellen? Sagen Sie Ja oder Nein."
            )
            await self._speak_to_caller(turn_context, call_summary_text)
        else:
            await turn_context.send_activity(MessageFactory.text(summary_filled))
            await turn_context.send_activity(
                MessageFactory.suggested_actions(
                    SuggestedActions(
                        actions=[
                            CardAction(
                                title="Ja, Konto erstellen",
                                type=ActionTypes.im_back,
                                value="Ja"
                            ),
                            CardAction(
                                title="Nein, abbrechen",
                                type=ActionTypes.im_back,
                                value="Nein"
                            )
                        ]
                    )
                )
            )

        await self.dialog_state_accessor.set(turn_context, DialogState.FINAL_CONFIRMATION)


    async def _handle_final_confirmation(self, turn_context: TurnContext, user_profile: Dict, user_input: str):
        """Behandelt die finale Bestätigung und speichert die Daten."""
        user_input_lower = user_input.lower().strip()
        is_call = self._is_call_context(turn_context)

        if user_input_lower in ["ja", "j", "yes", "y", "richtig", "korrekt", "ok"]:
            success = await self._save_customer_data(user_profile)
            if success:
                success_msg = "Ihre Daten wurden erfolgreich gespeichert! Ihr Konto wurde erstellt. Vielen Dank für Ihre Registrierung! Sie können mich jederzeit erneut ansprechen, wenn Sie Fragen haben."
                if is_call:
                    await self._speak_to_caller(turn_context, success_msg)
                    # Am Ende eines Anrufs kann der Bot auflegen
                    # (Würde hier eine Graph API call to hangup erfordern)
                else:
                    await turn_context.send_activity(MessageFactory.text(success_msg))
                await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
                await self.user_profile_accessor.set(turn_context, {}) # Profil zurücksetzen
            else:
                error_msg = "Entschuldigung, beim Speichern Ihrer Daten ist ein Problem aufgetreten. Bitte versuchen Sie es später erneut."
                if is_call:
                    await self._speak_to_caller(turn_context, error_msg)
                else:
                    await turn_context.send_activity(MessageFactory.text(error_msg))
                await self.dialog_state_accessor.set(turn_context, DialogState.ERROR)
        elif user_input_lower in ["nein", "n", "no", "falsch", "inkorrekt"]:
            cancel_msg = "Registrierung abgebrochen. Sie können jederzeit neu starten."
            if is_call:
                await self._speak_to_caller(turn_context, cancel_msg)
                # Am Ende eines Anrufs kann der Bot auflegen
            else:
                await turn_context.send_activity(MessageFactory.text(cancel_msg))
            await self.dialog_state_accessor.set(turn_context, DialogState.GREETING) # Zustand zurücksetzen
            await self.user_profile_accessor.set(turn_context, {}) # Profil leeren
        else:
            prompt_msg = "Bitte antworten Sie mit 'ja' oder 'nein'."
            if is_call:
                await self._speak_to_caller(turn_context, prompt_msg)
            else:
                await turn_context.send_activity(MessageFactory.text(prompt_msg))


    # === VALIDATION AND HELPER METHODS ===

    def _validate_name_part(self, name: str) -> bool:
        """Validiert Vornamen und Nachnamen."""
        return len(name.strip()) >= 2 and re.match(r'^[a-zA-ZäöüÄÖÜß\s\-\']+$', name.strip()) is not None

    def _parse_birthdate(self, date_str: str) -> Optional[datetime.date]:
        """
        Versucht, Geburtsdatum aus verschiedenen Formaten zu parsen und zu validieren.
        Unterstützt TT.MM.JJJJ und versucht, gesprochene Datumsangaben zu interpretieren.
        """
        date_str = date_str.lower().strip()

        # Versuche numerisches TT.MM.JJJJ Format
        try:
            date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
            if self._is_valid_age(date_obj):
                return date_obj
        except ValueError:
            pass

        # Versuche, gesprochene Datumsangaben zu interpretieren (sehr einfach gehalten)
        # Realistisch würde hier ein NLU-Modell (wie CLU) oder eine Bibliothek zur Datums-Erkennung benötigt.
        month_map = {
            "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
            "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
        }

        # Beispiel: "fünfzehnter märz neunzehnhundertneunzig"
        match = re.search(r'(\d+|er|ter|ster)\s*(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)\s*(\d{4})', date_str)
        if match:
            day_str = match.group(1).replace("er", "").replace("ter", "").replace("ster", "") # "15er" -> "15"
            month_name = match.group(2)
            year_str = match.group(3)
            try:
                day = int(day_str)
                month = month_map[month_name]
                year = int(year_str)
                date_obj = datetime(year, month, day).date()
                if self._is_valid_age(date_obj):
                    return date_obj
            except (ValueError, KeyError):
                pass

        return None

    def _is_valid_age(self, date_obj: datetime.date) -> bool:
        """Prüft, ob das Geburtsdatum ein realistisches Alter repräsentiert."""
        today = datetime.now().date()
        age = today.year - date_obj.year - ((today.month, today.day) < (date_obj.month, date_obj.day))
        return 0 <= age < 120 # Realistisches Alter zwischen 0 und 120 Jahre

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

    def _normalize_spoken_email(self, email_str: str) -> str:
        """
        Normalisiert eine gesprochene E-Mail-Adresse.
        Ersetzt gängige gesprochene Formen ('at', 'dot') durch Symbole.
        """
        normalized = email_str.lower().strip()
        normalized = normalized.replace(" at ", "@").replace(" dot ", ".").replace(" underscore ", "_")
        normalized = normalized.replace(" punkt ", ".").replace(" minus ", "-").replace(" unterstrich ", "_")
        # Weitere Ersetzungen nach Bedarf
        return normalized

    def _validate_phone(self, phone_str: str) -> Optional[PhoneNumber]:
        """Validiert eine deutsche Telefonnummer und gibt ein PhoneNumber-Objekt zurück."""
        try:
            # Versuche, die Standardregion DE (Deutschland) zu verwenden
            parsed_number = parse(phone_str, "DE")
            if is_valid_number(parsed_number):
                return PhoneNumber.from_string(phone_str, region="DE")
            else:
                # Fallback für internationale Nummern, wenn DE nicht passt
                parsed_number = parse(phone_str, None) # Ohne Standardregion
                if is_valid_number(parsed_number):
                    return PhoneNumber.from_string(phone_str, region=parsed_number.country_code)
        except NumberParseException:
            pass
        return None

    def _normalize_spoken_phone(self, phone_str: str) -> str:
        """
        Normalisiert eine gesprochene Telefonnummer.
        Entfernt Leerzeichen, Klammern, etc. und ersetzt "null" durch "0".
        """
        normalized = phone_str.lower().strip()
        normalized = re.sub(r'\s+', '', normalized) # Entfernt alle Leerzeichen
        normalized = normalized.replace("null", "0")
        normalized = normalized.replace("plus", "+")
        # Entferne andere nicht-numerische Zeichen, außer "+"
        normalized = re.sub(r'[^\d+]', '', normalized)
        return normalized


    def _validate_postal_code(self, postal_code: str) -> bool:
        """Validiert eine deutsche Postleitzahl (5 Ziffern)."""
        return re.match(r'^\d{5}$', postal_code.strip()) is not None

    # === CLU/LUIS Intent Extraction ===

    def _extract_intent_from_clu(self, clu_result: Dict) -> Dict:
        """Extrahiert den Top-Intent und Entitäten aus dem CLU-Ergebnis."""
        intent = clu_result.get("topIntent", "None")
        entities = clu_result.get("entities", [])
        return {"intent": intent, "entities": entities}

    def _extract_intent_simple(self, text: str) -> Dict:
        """
        Vereinfachte Intent-Erkennung als Fallback, falls CLU nicht verfügbar ist.
        Ersetzt LUIS/CLU durch einfache Stichwort-Erkennung.
        """
        text_lower = text.lower()
        if "hallo" in text_lower or "hi" in text_lower:
            return {"intent": "Greeting", "entities": []}
        if "hilfe" in text_lower or "helfen" in text_lower:
            return {"intent": "Help", "entities": []}
        if "danke" in text_lower or "auf wiedersehen" in text_lower or "ende" in text_lower:
            return {"intent": "EndConversation", "entities": []}
        # Hier könnten weitere einfache Regeln hinzugefügt werden,
        # um auf bestimmte Eingaben im Registrierungsprozess zu reagieren.
        return {"intent": "None", "entities": []} # "None" bedeutet, dass es an den Dialog-Handler geht.

    # === SPEZIFISCHE INTENT HANDLERS (für Text-Chat) ===
    # Diese könnten auch für Anrufe angepasst werden, wenn die CLU-Erkennung dort genutzt wird.

    async def _handle_greeting_intent(self, turn_context: TurnContext):
        """Behandelt den Begrüßungs-Intent."""
        # Startet den Registrierungsprozess neu oder fährt fort
        await self._initialize_conversation(turn_context) # Setzt den Dialog zurück
        await self._handle_greeting(turn_context, {}) # Ruft die Begrüßung auf

    async def _handle_help_intent(self, turn_context: TurnContext):
        """Behandelt den Hilfe-Intent."""
        help_message = "Ich bin hier, um Ihnen bei der Kundenregistrierung zu helfen. Bitte folgen Sie den Anweisungen, die ich Ihnen gebe."
        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, help_message)
        else:
            await turn_context.send_activity(MessageFactory.text(help_message))

    async def _handle_goodbye_intent(self, turn_context: TurnContext):
        """Behandelt den Abschieds-Intent."""
        goodbye_message = "Auf Wiedersehen! Vielen Dank für die Nutzung unseres Dienstes."
        if self._is_call_context(turn_context):
            await self._speak_to_caller(turn_context, goodbye_message)
            # Hier könnte auch ein Auflegen des Anrufs über die Graph API initiiert werden.
            # print(f"DEBUG: Initiating hangup for call {call_info.get('call_id')}", file=sys.stdout)
            # await self._hangup_call(turn_context, call_info.get('call_id'))
        else:
            await turn_context.send_activity(MessageFactory.text(goodbye_message))

        await self.dialog_state_accessor.set(turn_context, DialogState.COMPLETED)
        await self.user_profile_accessor.set(turn_context, {}) # Profil leeren
        await self.call_state_accessor.set(turn_context, CallState.IDLE) # Call-State zurücksetzen


    # === Datenbank-Speicherlogik (asynchron) ===

    async def _save_customer_data(self, user_profile: dict) -> bool:
        """
        Speichert die gesammelten Benutzerdaten in den Django-Modellen.
        Alle Datenbankoperationen sind asynchron umschlossen.
        """
        try:
            # Hilfsfunktionen für asynchrone Django ORM-Aufrufe
            async def _get_or_create_async(model, **kwargs):
                return await sync_to_async(model.objects.get_or_create)(**kwargs)

            async def _create_async(model, **kwargs):
                return await sync_to_async(model.objects.create)(**kwargs)

            country_obj, _ = await _get_or_create_async(
                AddressCountry, country_name=user_profile['country_name']
            )

            street_obj, _ = await _get_or_create_async(
                AddressStreet, street_name=user_profile['street_name']
            )

            # Annahme: City wird mit postal_code als unique_together Feld erstellt
            city_obj, _ = await _get_or_create_async(
                AddressCity, city_name=user_profile['city'], postal_code=user_profile['postal_code']
            )

            address_obj = await _create_async(
                Address,
                street=street_obj,
                house_number=user_profile['house_number'],
                house_number_addition=user_profile['house_number_addition'],
                city=city_obj,
                country=country_obj
            )

            customer_obj = await _create_async(
                Customer,
                gender=user_profile['gender'],
                title=user_profile['title'],
                first_name=user_profile['first_name'],
                last_name=user_profile['last_name'],
                birth_date=datetime.strptime(user_profile['birth_date'], '%Y-%m-%d').date(),
                address=address_obj
            )

            await _create_async(
                CustomerContact,
                customer=customer_obj,
                email=user_profile['email'],
                telephone=user_profile['telephone']
            )
            return True
        except Exception as e:
            print(f"❌ Fehler beim Speichern der Kundendaten: {e}", file=sys.stderr)
            return False

