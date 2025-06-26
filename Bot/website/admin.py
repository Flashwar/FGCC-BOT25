from django.contrib import admin
from Bot.models import (
    AddressCountry, AddressStreet, AddressCity, Address,
    Customer, CustomerContact
)


@admin.register(AddressCountry)
class AddressCountryAdmin(admin.ModelAdmin):
    list_display = ['country_name']
    search_fields = ['country_name']

@admin.register(AddressStreet)
class AddressStreetAdmin(admin.ModelAdmin):
    list_display = ['street_name']
    search_fields = ['street_name']

@admin.register(AddressCity)
class AddressCityAdmin(admin.ModelAdmin):
    list_display = ['city', 'postal_code', 'country']
    search_fields = ['city', 'postal_code']
    list_filter = ['country']

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['street', 'house_number', 'house_number_addition', 'place']
    search_fields = ['house_number', 'house_number_addition']
    list_filter = ['place', 'street']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'gender', 'first_name', 'second_name', 'title', 'birth_date', 'get_age']
    search_fields = ['first_name', 'second_name']
    list_filter = ['gender', 'title']
    autocomplete_fields = ['address']

    def get_age(self, obj):
        return obj.calculate_age()
    get_age.short_description = 'Alter'

@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ['customer', 'email', 'telephone']
    search_fields = ['email', 'telephone']
    autocomplete_fields = ['customer']




