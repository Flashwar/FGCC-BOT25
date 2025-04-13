from django.contrib import admin

from Bot.models import Customer, Birthday, Address, AddressCountry, AddressCity, AddressStreet

admin.site.register(Customer)
admin.site.register(Birthday)
admin.site.register(Address)
admin.site.register(AddressCountry)
admin.site.register(AddressCity)
admin.site.register(AddressStreet)



