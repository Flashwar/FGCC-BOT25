import django_filters
from .models import Customer

import django_filters
from django_filters import DateFromToRangeFilter
from django_filters.widgets import RangeWidget
from .models import Customer


class CustomerFilter(django_filters.FilterSet):
    first_name = django_filters.CharFilter(lookup_expr='icontains', label="Vorname")
    second_name = django_filters.CharFilter(lookup_expr='icontains', label="Nachname")
    #title = django_filters.ChoiceFilter(choices=Customer.TitleChoices.choices, label="Titel")
    #gender = django_filters.ChoiceFilter(choices=Customer.GenderChoice.choices, label="Geschlecht")
    address__place__city = django_filters.CharFilter(lookup_expr='icontains', label="Stadt")
    address__place__country__country_name = django_filters.CharFilter(lookup_expr='icontains', label="Land")
    birth_date = DateFromToRangeFilter(
        label="Geburtsdatum (von – bis)",
        widget=RangeWidget(attrs={
            'type': 'date',
            'class': 'form-control',
        })
    )

    title = django_filters.ChoiceFilter(
        choices=Customer.TitleChoices.choices,
        label="Titel",
        empty_label="Alle Titel"
    )

    gender = django_filters.ChoiceFilter(
        choices=Customer.GenderChoice.choices,
        label="Geschlecht",
        empty_label="Alle Geschlechter"
    )

    class Meta:
        model = Customer
        fields = [
            'first_name',
            'second_name',
            'gender',
            'title',
            'address__place__city',
            'address__place__country__country_name',
            'birth_date',
        ]
