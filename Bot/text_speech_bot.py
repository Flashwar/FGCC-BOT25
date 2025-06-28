class SpeechBotMessages:
    # Messages for the registration bot

    WELCOME_MESSAGE = (
        "**Willkommen!**\n\n"
        "Ich helfe Ihnen, ein Kundenkonto zu erstellen. Dafür frage ich einige Daten wie Name, E-Mail, Adresse ab.\n\n"
        "**Ihre Daten sind sicher und werden nur zur Kontoverwaltung genutzt.**\n\n"
        "**Sind Sie einverstanden?**\n"
        "Antworten Sie mit **'Ja'** oder **'Nein'**"
    )

    CONSENT_GRANTED = "**Danke!** Die Registrierung startet jetzt. Zuerst: Ihr Geschlecht."
    CONSENT_DENIED = "**Registrierung abgebrochen.** Wenn Sie es sich anders überlegen, sagen Sie einfach 'Hallo'."
    CONSENT_UNCLEAR = "**Unklar.** Bitte antworten Sie mit **'Ja'** oder **'Nein'**."


    # === FIELD PROMPTS ===
    FIELD_PROMPTS = {
        'gender': "Geschlecht?\n1 Männlich\n2 Weiblich\n3 Divers\n4 Keine Angabe",
        'title': "Haben Sie einen Titel? (z.B. Dr., Prof., Ph.D.)\nOder 'kein':",
        'first_name': "Ihr **Vorname**:",
        'last_name': "Ihr **Nachname**:",
        'birthdate': "Geburtsdatum (TT.MM.JJJJ):",
        'email': "Ihre **E-Mail-Adresse**:",
        'phone': "Ihre **Telefonnummer**:",
        'street': "Ihre **Straße** (ohne Nr.):",
        'house_number': "Ihre **Hausnummer**:",
        'house_addition': "Zusatz zur Hausnummer (oder 'kein'):",
        'postal': "Ihre **Postleitzahl**:",
        'city': "Ihr **Ort**:",
        'country': "Ihr **Land**:"
    }

    VALIDATION_ERRORS = {
        'gender': "Bitte wählen Sie 1-4 oder geben Sie das Geschlecht ein.",
        'title': "Geben Sie einen gültigen Titel oder 'kein' ein.",
        'first_name': "Vornamen mit mindestens 2 Buchstaben eingeben.",
        'last_name': "Nachnamen mit mindestens 2 Buchstaben eingeben.",
        'birthdate': "Geburtsdatum im Format TT.MM.JJJJ.",
        'email': "Bitte gültige E-Mail eingeben.",
        'phone': "Bitte gültige Telefonnummer eingeben.",
        'street': "Straßenname mit mind. 3 Buchstaben.",
        'house_number': "Geben Sie eine positive Zahl ein.",
        'postal': "PLZ mit 5 Ziffern eingeben.",
        'city': "Stadtname mit mind. 2 Buchstaben.",
        'country': "Ländercode oder Name eingeben.",
        'email_exists': "Diese E-Mail ist bereits registriert."
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
        "**Nicht erkannt.**\nWählen Sie eine Zahl (1-13), Feldnamen, 'Zurück' oder 'Neustart'."
    )

    RESTART_MESSAGE = "**Neustart...** Alle Eingaben werden gelöscht."

    REGISTRATION_SUCCESS = (
        "**Registrierung abgeschlossen!**\nIhr Konto wurde erstellt.\nVielen Dank!"
    )

    SAVE_ERROR = "**Fehler beim Speichern.**\n'Nochmal' - wiederholen\n'Neustart' - von vorne"
    SAVE_IN_PROGRESS = "**Speichere Daten...**"

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
        "**Unklar.**\n'Ja' - speichern\n'Nein' - korrigieren\n'Neustart' - neu beginnen"
    )

    RESTART_NEW_REGISTRATION = (
        "**Möchten Sie neu starten?**\nIch beginne gerne von vorne."
    )

    ALREADY_REGISTERED = (
        "**Bereits registriert.**\nBei Änderungen wenden Sie sich an den Support."
    )

    REGISTRATION_CANCELLED_HELP = (
        "**Abgebrochen.**\nSagen Sie 'Hallo' für eine neue Registrierung."
    )

    ALREADY_COMPLETED_HELP = (
        "**Registrierung abgeschlossen.**\nSagen Sie 'Hallo', um erneut zu starten."
    )

    # === ERROR MESSAGES ===
    UNKNOWN_STATE_RESTART = "**Neustart erkannt.** Neue Registrierung beginnt."
    UNKNOWN_STATE_CONFUSION = "**Fehler im Dialog.** Sagen Sie 'Hallo', um neu zu starten."
    ERROR_HELP = "**Fehler aufgetreten.**\n'Nochmal', 'Neustart' oder 'Zurück'?"
    CORRECTION_HELP = (
        "**Korrekturhilfe:**\nZahl oder Feldname eingeben\nBeispiel: '6' oder 'email'\n"
        "'Zurück' - Übersicht\n'Neustart' - neu starten"
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