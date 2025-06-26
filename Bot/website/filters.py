import django_filters
from django_filters import DateFromToRangeFilter
from django_filters.widgets import RangeWidget
from Bot.models import Customer

# FilterSet for the Customer model
class CustomerFilter(django_filters.FilterSet):
    first_name = django_filters.CharFilter(lookup_expr='icontains', label="Vorname")
    second_name = django_filters.CharFilter(lookup_expr='icontains', label="Nachname")
    address__place__city = django_filters.CharFilter(lookup_expr='icontains', label="Stadt")
    address__place__country__country_name = django_filters.CharFilter(lookup_expr='icontains', label="Land")

    # Filter for birth date range using a dual date input widget
    birth_date = DateFromToRangeFilter(
        label="Geburtsdatum (von – bis)",
        widget=RangeWidget(attrs={
            'type': 'date',
            'class': 'form-control',
        })
    )

    # Dropdown filter for academic title with optional empty selection
    title = django_filters.ChoiceFilter(
        choices=Customer.TitleChoices.choices,
        label="Titel",
        empty_label="Alle Titel"
    )

    # Dropdown filter for gender with optional empty selection
    gender = django_filters.ChoiceFilter(
        choices=Customer.GenderChoice.choices,
        label="Geschlecht",
        empty_label="Alle Geschlechter"
    )

    # specifying the model and filterable fields
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
