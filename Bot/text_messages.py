
class BotMessages:
    # Messages for the registration bot

    WELCOME_MESSAGE = (
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

    CONSENT_GRANTED = (
        "**Vielen Dank für Ihr Einverständnis!**\n\n"
        "Die Registrierung beginnt jetzt. Lassen Sie uns mit Ihrem Geschlecht beginnen."
    )

    CONSENT_DENIED = (
        "**Registrierung abgebrochen**\n\n"
        "Ich verstehe, dass Sie nicht fortfahren möchten. "
        "Die Registrierung wurde beendet.\n\n"
        "Falls Sie Ihre Meinung ändern, können Sie jederzeit eine neue "
        "Konversation beginnen und 'Hallo' sagen.\n\n"
        "Haben Sie noch einen schönen Tag!"
    )

    CONSENT_UNCLEAR = (
        " **Entschuldigung, das habe ich nicht verstanden.**\n\n"
        "Bitte antworten Sie klar mit:\n"
        "**'Ja'** - um mit der Registrierung fortzufahren\n"
        " **'Nein'** - um den Prozess abzubrechen\n\n"
        "**Sind Sie einverstanden mit dem Registrierungsprozess?**"
    )

    # === FIELD PROMPTS ===
    FIELD_PROMPTS = {
        'gender': (
            "Bitte wählen Sie Ihr Geschlecht:\n\n"
            "1 **Männlich**\n"
            "2 **Weiblich**\n"
            "3 **Divers**\n"
            "4 **Keine Angabe**\n\n"
            "Sie können die Nummer oder den Begriff eingeben."
        ),
        'title': (
            "Haben Sie einen akademischen Titel? (optional)\n\n"
            "**Verfügbare Titel:**\n"
            "• Dr.\n• Prof.\n• Prof. Dr.\n• Prof. Dr. Dr.\n"
            "• Dipl.-Ing.\n• Dr.-Ing.\n• Dr. phil.\n• Dr. jur.\n"
            "• Dr. med.\n• Mag.\n• Lic.\n• Ph.D.\n\n"
            "Geben Sie Ihren Titel ein oder **'kein'** für keinen Titel:"
        ),
        'first_name': "Bitte geben Sie Ihren **Vornamen** ein:",
        'last_name': "Bitte geben Sie Ihren **Nachnamen** ein:",
        'birthdate': (
            "Bitte geben Sie Ihr **Geburtsdatum** ein (Format: TT.MM.JJJJ):\n\n"
            "Beispiel: 15.03.1990"
        ),
        'email': "Bitte geben Sie Ihre **E-Mail-Adresse** ein:",
        'phone': (
            "Bitte geben Sie Ihre **Telefonnummer** ein:\n\n"
            "Beispiele:\n"
            "• +49 30 12345678\n"
            "• 030 12345678\n"
            "• 0175 1234567"
        ),
        'street': (
            "Bitte geben Sie Ihre **Straße** ein (ohne Hausnummer):\n\n"
            "Beispiel: Musterstraße"
        ),
        'house_number': "Bitte geben Sie Ihre **Hausnummer** ein:\n\nBeispiel: 42",
        'house_addition': (
            "Haben Sie einen **Hausnummernzusatz**? (optional)\n\n"
            "Beispiele: a, b, 1/2, links\n\n"
            "Geben Sie den Zusatz ein oder **'kein'** für keinen Zusatz:"
        ),
        'postal': "Bitte geben Sie Ihre **Postleitzahl** ein:\n\nBeispiel: 12345",
        'city': "Bitte geben Sie Ihren **Ort/Stadt** ein:\n\nBeispiel: Berlin",
        'country': "Bitte geben Sie Ihr **Land** ein:\n\nBeispiel: Deutschland"
    }

    VALIDATION_ERRORS = {
        'gender': "Bitte wählen Sie eine gültige Option (1-4) oder geben Sie das Geschlecht direkt ein.",
        'title': "Bitte wählen Sie einen gültigen Titel aus der Liste oder geben Sie 'kein' ein.",
        'first_name': "Bitte geben Sie einen gültigen Vornamen ein (mindestens 2 Zeichen, nur Buchstaben):",
        'last_name': "Bitte geben Sie einen gültigen Nachnamen ein (mindestens 2 Zeichen):",
        'birthdate': "Bitte geben Sie ein gültiges Geburtsdatum im Format TT.MM.JJJJ ein:",
        'email': "Bitte geben Sie eine gültige E-Mail-Adresse ein:",
        'phone': "Bitte geben Sie eine gültige deutsche Telefonnummer ein:",
        'street': "Bitte geben Sie eine gültige Straße ein (mindestens 3 Zeichen, nur Buchstaben und Leerzeichen):",
        'house_number': "Bitte geben Sie eine gültige Hausnummer (positive Zahl) ein:",
        'postal': "Bitte geben Sie eine gültige deutsche Postleitzahl (5 Ziffern) ein:",
        'city': "Bitte geben Sie einen gültigen Ort ein (mindestens 2 Zeichen, nur Buchstaben und Leerzeichen):",
        'country': "Bitte geben Sie ein gültiges Land ein (mindestens 2 Zeichen, nur Buchstaben und Leerzeichen):",
        'email_exists': "Diese E-Mail-Adresse ist bereits registriert. Bitte geben Sie eine andere E-Mail ein."
    }

    @staticmethod
    def confirmation_prompt(field_name: str, value: str) -> str:
        return f"{field_name}: **{value}**\n\nIst das korrekt? (ja/nein)"

    CONFIRMATION_REJECTED = "Okay, lassen Sie uns das korrigieren."
    CONFIRMATION_UNCLEAR = "Bitte antworten Sie mit 'ja' oder 'nein'."

    CORRECTION_OPTIONS = (
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

    @staticmethod
    def correction_start(field_display: str) -> str:
        return (
            f"**Korrektur: {field_display}**\n\n"
            f"Sie möchten {field_display} ändern. "
            f"Bitte geben Sie den neuen Wert ein:"
        )

    @staticmethod
    def correction_success(field_display: str, new_value: str) -> str:
        return (
            f"✅ **{field_display} korrigiert!**\n\n"
            f"Neuer Wert: {new_value}\n\n"
            f"Zurück zur Zusammenfassung..."
        )

    CORRECTION_NOT_UNDERSTOOD = (
        "**Ich habe das nicht verstanden.**\n\n"
        "Bitte wählen Sie:\n"
        "• **Eine Nummer** (1-13)\n"
        "• **Einen Feldnamen** (z.B. 'Email', 'Adresse')\n"
        "• **'Zurück'** zur Zusammenfassung\n"
        "• **'Neustart'** für kompletten Neustart\n\n"
        "**Was möchten Sie korrigieren?**"
    )

    RESTART_MESSAGE = (
        "**Neustart wird gestartet...**\n\n"
        "Alle bisherigen Eingaben werden gelöscht und wir beginnen von vorne."
    )

    REGISTRATION_SUCCESS = (
        "**Registrierung erfolgreich abgeschlossen!**\n\n"
        "Ihre Daten wurden erfolgreich gespeichert\n"
        "Ihr Kundenkonto wurde erstellt\n\n"
        "Vielen Dank für Ihre Registrierung! 😊"
    )

    SAVE_ERROR = (
        "**Fehler beim Speichern**\n\n"
        "Entschuldigung, beim Speichern ist ein Problem aufgetreten.\n"
        "• **'Nochmal'** - erneut versuchen\n"
        "• **'Neustart'** - von vorne beginnen"
    )

    SAVE_IN_PROGRESS = " **Speichere Ihre Daten...**"


    @staticmethod
    def final_summary(user_profile: dict) -> str:
        title_text = user_profile.get('title_display', 'Kein Titel')

        return (
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

    FINAL_CONFIRMATION_UNCLEAR = (
        "**Bitte präzisieren Sie:**\n\n"
        "• **'Ja'** - alle Daten sind korrekt, Konto erstellen\n"
        "• **'Nein'** - ich möchte etwas korrigieren\n"
        "• **'Neustart'** - komplett von vorne beginnen"
    )


    RESTART_NEW_REGISTRATION = (
        "**Neue Registrierung starten**\n\n"
        "Möchten Sie es nochmal versuchen? Ich starte gerne eine neue Registrierung für Sie.\n\n"
        "Hier nochmal die Information zu unserem Prozess:"
    )

    ALREADY_REGISTERED = (
        "**Registrierung bereits abgeschlossen**\n\n"
        "Sie haben sich bereits erfolgreich registriert! "
        "Falls Sie Änderungen vornehmen möchten, wenden Sie sich bitte an unseren Support.\n\n"
        "Haben Sie noch andere Fragen?"
    )

    REGISTRATION_CANCELLED_HELP = (
        "**Registrierung wurde abgebrochen**\n\n"
        "Falls Sie Ihre Meinung geändert haben, sagen Sie einfach:\n"
        "• **'Hallo'** oder **'Neu'** - um eine neue Registrierung zu starten\n\n"
        "Ansonsten helfe ich Ihnen gerne bei anderen Fragen."
    )

    ALREADY_COMPLETED_HELP = (
        "**Registrierung bereits abgeschlossen**\n\n"
        "Ihre Registrierung war erfolgreich! Bei Fragen wenden Sie sich bitte an unseren Support.\n\n"
        "Oder sagen Sie **'Hallo'** um eine neue Registrierung für eine andere Person zu starten."
    )

    # === ERROR MESSAGES ===
    UNKNOWN_STATE_RESTART = (
        "**Neustart erkannt**\n\n"
        "Ich starte eine neue Registrierung für Sie."
    )

    UNKNOWN_STATE_CONFUSION = (
        "**Entschuldigung, ich bin verwirrt.**\n\n"
        "Es scheint ein Problem mit dem Dialog-Verlauf aufgetreten zu sein.\n\n"
        "Sagen Sie einfach **'Hallo'** um eine neue Registrierung zu beginnen."
    )

    ERROR_HELP = (
        "❌ **Ein Fehler ist aufgetreten.**\n\n"
        "**Was möchten Sie tun?**\n"
        "• **'Nochmal'** - erneut versuchen zu speichern\n"
        "• **'Neustart'** - komplett von vorne beginnen\n"
        "• **'Zurück'** - zur Zusammenfassung zurückkehren"
    )

    # === HELP MESSAGES ===
    CORRECTION_HELP = (
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


class FieldConfig:

    FIELD_DISPLAY_NAMES = {
        'gender': 'Geschlecht',
        'title': 'Titel',
        'first_name': 'Vorname',
        'last_name': 'Nachname',
        'birthdate': 'Geburtsdatum',
        'email': 'E-Mail',
        'phone': 'Telefonnummer',
        'street': 'Straße',
        'house_number': 'Hausnummer',
        'house_addition': 'Hausnummernzusatz',
        'postal': 'Postleitzahl',
        'city': 'Ort',
        'country': 'Land'
    }

    # Mapping for correction selection
    CORRECTION_MAPPING = {
        # Numbers
        "1": "gender", "2": "title", "3": "first_name", "4": "last_name",
        "5": "birthdate", "6": "email", "7": "phone", "8": "street",
        "9": "house_number", "10": "house_addition", "11": "postal",
        "12": "city", "13": "country",

        # German field names
        "geschlecht": "gender", "titel": "title", "vorname": "first_name",
        "nachname": "last_name", "name": "first_name", "geburtsdatum": "birthdate",
        "geburtstag": "birthdate", "email": "email", "e-mail": "email",
        "mail": "email", "telefon": "phone", "phone": "phone", "handy": "phone",
        "straße": "street", "strasse": "street", "adresse": "street",
        "hausnummer": "house_number", "nummer": "house_number",
        "hausnummernzusatz": "house_addition", "zusatz": "house_addition",
        "plz": "postal", "postleitzahl": "postal", "ort": "city",
        "stadt": "city", "city": "city", "land": "country", "country": "country"
    }

    # Valid options for specific fields
    GENDER_OPTIONS = {
        "1": ("male", "Männlich"), "männlich": ("male", "Männlich"), "male": ("male", "Männlich"),
        "2": ("female", "Weiblich"), "weiblich": ("female", "Weiblich"), "female": ("female", "Weiblich"),
        "3": ("diverse", "Divers"), "divers": ("diverse", "Divers"), "diverse": ("diverse", "Divers"),
        "4": ("unspecified", "Keine Angabe"), "keine angabe": ("unspecified", "Keine Angabe"),
        "unspecified": ("unspecified", "Keine Angabe"),
    }

    VALID_TITLES = [
        "Dr.", "Prof.", "Prof. Dr.", "Prof. Dr. Dr.", "Dipl.-Ing.",
        "Dr.-Ing.", "Dr. phil.", "Dr. jur.", "Dr. med.", "Mag.", "Lic.", "Ph.D."
    ]

    NO_TITLE_KEYWORDS = ["kein", "keiner", "nein", "keine", "-", "none", ""]
    NO_ADDITION_KEYWORDS = ["kein", "keiner", "nein", "keine", "-", ""]

    # Response keywords
    POSITIVE_RESPONSES = [
        'ja', 'yes', 'ok', 'okay', 'einverstanden', 'zustimmung',
        'zustimmen', 'akzeptieren', 'weiter', 'fortfahren', 'gerne',
        'si', 'oui', 'sí', '✓', '👍', 'y'
    ]

    NEGATIVE_RESPONSES = [
        'nein', 'no', 'nicht einverstanden', 'ablehnen', 'abbrechen',
        'stop', 'halt', 'nee', 'nö', 'non', '✗', '👎', 'n'
    ]

    CONFIRMATION_YES = ["ja", "j", "yes", "y", "richtig", "korrekt", "ok"]
    CONFIRMATION_NO = ["nein", "n", "no", "falsch", "inkorrekt"]

    RESTART_KEYWORDS = [
        'hallo', 'hello', 'hi', 'neu', 'nochmal', 'wieder', 'start',
        'registrierung', 'anmelden', 'beginnen', 'restart', 'new'
    ]