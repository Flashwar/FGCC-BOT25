import uuid

from django.db import models
from django.utils.timezone import now
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _

class Birthday(models.Model):
    birth_date = models.DateField()

class AddressCountry(models.Model):
    country_name = models.CharField(max_length=100, unique=True, primary_key=True)

class AddressStreet(models.Model):
    street_name = models.CharField(max_length=100, unique=True, primary_key=True)

class AddressCity(models.Model):
    city = models.CharField(max_length=100, unique=False, primary_key=False)
    postal_code = models.CharField(max_length=10, unique=False, primary_key=False)
    country = models.ForeignKey(AddressCountry, on_delete=models.CASCADE, related_name='cities')

class Address(models.Model):
    street = models.ForeignKey(AddressStreet, on_delete=models.CASCADE, related_name='street')
    house_number = models.PositiveIntegerField(unique=False, primary_key=False)
    house_number_addition = models.CharField(max_length=10, unique=False, primary_key=False)
    place = models.ForeignKey(AddressCity, on_delete=models.CASCADE, related_name='cities')

class Customer(models.Model):
    customer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class GenderChoice(models.TextChoices):
        MALE = "Male", _("Herr")
        FEMALE = "Female", _("Frau")
        OTHERS = "Other", _("Genderneutral")

    gender = models.CharField(max_length=10, unique=False, primary_key=False, choices=GenderChoice.choices, blank=False)
    first_name = models.CharField(max_length=30, unique=False, primary_key=False)
    second_name = models.CharField(max_length=100, unique=False, primary_key=False)

    class TitleChoices(models.TextChoices):
        # Dr.", "Prof.", "Prof. Dr." oder leer
        DOCTOR_TITLE = "Dr.",_("Dr.")
        PROFESSOR_TITLE = "Prof.",_("Prof.")
        PROFESSOR_DOCTOR_TITLE = "Prof.Dr.",_("Prof. Dr.")

    title = models.CharField(max_length=100, unique=False, primary_key=False, choices=TitleChoices.choices, blank=True)
    birthdate = models.ForeignKey(Birthday, on_delete=models.CASCADE)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)

    def calculate_age(self):
        today = now().date()
        return today.year - self.birthdate.birth_date.year - ((today.month, today.day) < (self.birthdate.birth_date.month, self.birthdate.birth_date.day))

class CustomerContact(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    email = models.EmailField()
    telephone = PhoneNumberField()
