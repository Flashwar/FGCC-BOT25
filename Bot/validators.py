import re
from datetime import datetime
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from phonenumbers import NumberParseException, parse, is_valid_number
from phonenumber_field.phonenumber import PhoneNumber

class DataValidator:

    @staticmethod
    def validate_name_part(name: str):
        # Validates first or last name
        # Must contain only letters, hyphens, or apostrophes and be at least 2 characters
        if not name or len(name.strip()) < 2:
            return False
        pattern = r"^[a-zA-ZäöüÄÖÜß\-']+$"
        return bool(re.match(pattern, name.strip()))

    @staticmethod
    def validate_birthdate(date_str: str):
        # Validates birthdate in format DD.MM.YYYY and ensures age is reasonable
        try:
            date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
            today = datetime.now().date()
            if date_obj < today and (today.year - date_obj.year) < 150:
                return date_obj
        except ValueError:
            pass
        return None

    @staticmethod
    def validate_email(email: str):
        # Validates email format using Django's built-in validator
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    @staticmethod
    def validate_phone(phone_str: str):
        # Validates German phone number and returns a PhoneNumber object if valid
        try:
            parsed_number = parse(phone_str, "DE")
            if is_valid_number(parsed_number):
                return PhoneNumber.from_string(phone_str, region="DE")
        except NumberParseException:
            pass
        return None

    @staticmethod
    def validate_postal_code(postal_code: str):
        # Validates German postal code (exactly 5 digits)
        return bool(re.match(r'^\d{5}$', postal_code))

    @staticmethod
    def validate_house_number(house_number: str):
        # Validates house number which can be digits optionally followed by a letter
        pattern = r'^\d+[a-zA-Z]?$'
        return bool(re.match(pattern, house_number.strip()))

    @staticmethod
    def validate_city_name(city: str):
        # Validates city name allowing letters, spaces, hyphens, and apostrophes
        if not city or len(city.strip()) < 2:
            return False
        pattern = r"^[a-zA-ZäöüÄÖÜß\s\-']+$"
        return bool(re.match(pattern, city.strip()))

    @staticmethod
    def validate_street_name(street: str):
        # Validates street name allowing letters, spaces, hyphens, apostrophes, and dots
        if not street or len(street.strip()) < 2:
            return False
        pattern = r"^[a-zA-ZäöüÄÖÜß\s\-'.]+$"
        return bool(re.match(pattern, street.strip()))

    @staticmethod
    def validate_country_name(country: str):
        # Validates country name allowing letters, spaces, hyphens, and apostrophes
        if not country or len(country.strip()) < 2:
            return False
        pattern = r"^[a-zA-ZäöüÄÖÜß\s\-']+$"
        return bool(re.match(pattern, country.strip()))

# Instantiate the validator class for usage
validator = DataValidator()
