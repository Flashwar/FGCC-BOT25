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

            # Check if date is not in the future
            if date_obj >= today:
                return None

            # Calculate age in years
            age_years = today.year - date_obj.year
            if date_obj.month > today.month or (date_obj.month == today.month and date_obj.day > today.day):
                age_years -= 1

            # Check age bounds: must be between 16 and 120 years
            if age_years < 16 or age_years > 120:
                return None

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
        if not postal_code:
            return None

            # Remove whitespace and ensure it's a string
        postal_code = str(postal_code).strip()

        # German postal codes: 5 digits, range 01001-99998
        if not re.match(r'^\d{5}$', postal_code):
            return None

        postal_int = int(postal_code)

        # Valid German postal code range
        if postal_int < 1001 or postal_int > 99998:
            return None

        # Exclude invalid ranges (these don't exist in Germany)
        invalid_ranges = [
            (62000, 62999),
            (77000, 77999),
            (5000, 5999),
        ]

        for start, end in invalid_ranges:
            if start <= postal_int <= end:
                return None

        return postal_code

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
