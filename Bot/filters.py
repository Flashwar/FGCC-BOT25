import django_filters
from .models import Customer

class CustomerFilter(django_filters.FilterSet):
    first_name = django_filters.CharFilter(lookup_expr='icontains', label="Vorname")
    second_name = django_filters.CharFilter(lookup_expr='icontains', label="Nachname")
    title = django_filters.ChoiceFilter(choices=Customer.TitleChoices.choices, label="Titel")

    address__place__city = django_filters.CharFilter(lookup_expr='icontains', label="Stadt")
    address__place__country__country_name = django_filters.CharFilter(lookup_expr='icontains', label="Land")

    class Meta:
        model = Customer
        fields = ['first_name', 'second_name', 'title', 'address__place__city', 'address__place__country__country_name']
