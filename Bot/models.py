import uuid

from django.db import models
from django.utils.timezone import now
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _

# Country table with unique name as primary key
class AddressCountry(models.Model):
    country_name = models.CharField(max_length=100, unique=True, primary_key=True)

# Street table with unique name as primary key
class AddressStreet(models.Model):
    street_name = models.CharField(max_length=100, unique=True, primary_key=True)

    def __str__(self):
        return f"{self.street_name}"

# City table linked to country without unique constraint
class AddressCity(models.Model):
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.ForeignKey(AddressCountry, on_delete=models.CASCADE, related_name='cities')

    def __str__(self):
        return f"{self.city} ({self.postal_code})"

# Full address model referencing street and city
class Address(models.Model):
    street = models.ForeignKey(AddressStreet, on_delete=models.CASCADE, related_name='street')
    house_number = models.PositiveIntegerField()
    house_number_addition = models.CharField(max_length=10, blank=True)
    place = models.ForeignKey(AddressCity, on_delete=models.CASCADE, related_name='cities')

    def __str__(self):
        addition = f" {self.house_number_addition}" if self.house_number_addition else ""
        return f"{self.street.street_name} {self.house_number}{addition}, {self.place.postal_code} {self.place.city}, {self.place.country.country_name}"

# Customer model with gender, title, name, birth date and address
class Customer(models.Model):
    customer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class GenderChoice(models.TextChoices):
        MALE = "male", _("Männlich")
        FEMALE = "female", _("Weiblich")
        DIVERSE = "diverse", _("Divers")
        UNSPECIFIED = "unspecified", _("Keine Angabe")

    gender = models.CharField(max_length=15, choices=GenderChoice.choices)
    first_name = models.CharField(max_length=30)
    second_name = models.CharField(max_length=100)
    birth_date = models.DateField()

    class TitleChoices(models.TextChoices):
        DOCTOR = "Dr.", _("Dr.")
        PROFESSOR = "Prof.", _("Prof.")
        PROFESSOR_DOCTOR = "Prof. Dr.", _("Prof. Dr.")
        PROFESSOR_DOCTOR_MULTIPLE = "Prof. Dr. Dr.", _("Prof. Dr. Dr.")
        DIPLOMA_ENGINEER = "Dipl.-Ing.", _("Dipl.-Ing.")
        DOCTOR_ENGINEER = "Dr.-Ing.", _("Dr.-Ing.")
        DOCTOR_PHIL = "Dr. phil.", _("Dr. phil.")
        DOCTOR_JUR = "Dr. jur.", _("Dr. jur.")
        DOCTOR_MED = "Dr. med.", _("Dr. med.")
        MAGISTER = "Mag.", _("Mag.")
        LICENTIATE = "Lic.", _("Lic.")
        PHD = "Ph.D.", _("Ph.D.")
        NONE = '', _('Kein Titel')

    title = models.CharField(max_length=100, choices=TitleChoices.choices, blank=True, default=TitleChoices.NONE)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)

    # Returns the calculated age based on the birth date
    def calculate_age(self):
        today = now().date()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))

    def __str__(self):
        title = f"{self.title} " if self.title else ""
        return f"{title}{self.first_name} {self.second_name} ({self.get_gender_display()}), geb. {self.birth_date}"

# Contact information for a customer including email and phone number
class CustomerContact(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    email = models.EmailField()
    telephone = PhoneNumberField(region="DE")
