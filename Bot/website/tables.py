import django_tables2 as tables
from Bot.models import Customer, CustomerContact

# Table definition of displaying the customer data
class CustomerTable(tables.Table):
    full_name = tables.Column(empty_values=(), verbose_name="Name")
    address = tables.Column(empty_values=(), verbose_name="Adresse")
    email = tables.Column(empty_values=(), verbose_name="E-Mail")
    phone = tables.Column(empty_values=(), verbose_name="Telefon")
    birthday = tables.Column(accessor='birth_date', verbose_name="Geburtstag")

    class Meta:
        # Base Model
        model = Customer
        # Use Bootstrap 5 template
        template_name = "django_tables2/bootstrap5.html"
        # No default model fields used
        fields = ()

    # Render the full name with an optional title
    def render_full_name(self, record):
        title = f"{record.title}" if record.title else ""
        gender = f"{record.gender}" if record.gender else ""
        return f"{title} {record.first_name} {record.second_name} ({gender.capitalize() if gender else 'unbekannt'})"

    # Render a full address including street, house number, city, postal code, and country
    def render_address(self, record):
        addr = record.address
        city = addr.place
        return f"{addr.street.street_name} {addr.house_number}{addr.house_number_addition}, {city.postal_code} {city.city}, {city.country.country_name}"

    # Render corresponding email from related table CustomerContact
    def render_email(self, record):
        contact = CustomerContact.objects.filter(customer=record).first()
        return contact.email if contact else "-"

    # Render corresponding phone number from related table CustomerContact
    def render_phone(self, record):
        contact = CustomerContact.objects.filter(customer=record).first()
        return contact.telephone if contact else "-"
