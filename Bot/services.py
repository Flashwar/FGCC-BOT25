from injector import singleton
from django.db.models import Count
from Bot.models import Customer, AddressCountry, AddressStreet, AddressCity, Address, CustomerContact


@singleton
class CustomerService:
    """Service for all customer-related database operations"""

    def get_all_customers_with_relations(self):
        """
        Retrieves all customers along with their related address and country information.
        Uses select_related to optimize database queries.
        """
        return Customer.objects.select_related(
            'address__street',
            'address__place__country'
        ).all()

    def get_total_count(self):
        """
        Returns the total number of customers in the database.
        """
        return Customer.objects.count()

    def get_title_distribution(self):
        """
        Returns a distribution count of customers by title.
        """
        return list(Customer.objects.values('title').annotate(count=Count('title')))

    def get_gender_distribution(self):
        """
        Returns a distribution count of customers by gender.
        """
        return list(Customer.objects.values('gender').annotate(count=Count('gender')))

    def get_country_distribution(self):
        """
        Returns the number of customers grouped by their country.
        """
        return list(
            Customer.objects
            .values('address__place__country__country_name')
            .annotate(count=Count('customer_id'))
        )

    def get_customers_with_birth_dates(self):
        """
        Retrieves all customers who have a recorded birth date.
        Only returns customer ID and birth date for performance optimization.
        """
        return Customer.objects.exclude(birth_date__isnull=True).only('customer_id', 'birth_date')

    def create_full_customer(self, customer_data: dict, contact_data: dict, address_data: dict):
        """
        Creates a full customer record including related country, city, street, address, and contact data.

        Args:
            customer_data (dict): Dictionary containing customer personal data.
            contact_data (dict): Dictionary containing contact details like email and telephone.
            address_data (dict): Dictionary containing address details including country, city, and street.

        Returns:
            Customer: The created Customer instance.
        """

        # Create or get country
        country, _ = AddressCountry.objects.get_or_create(
            country_name=address_data["country_name"]
        )

        # Create or get city
        city, _ = AddressCity.objects.get_or_create(
            city=address_data["city"],
            postal_code=address_data["postal_code"],
            country=country
        )

        # Create or get street
        street, _ = AddressStreet.objects.get_or_create(
            street_name=address_data["street_name"]
        )

        # Create address
        address = Address.objects.create(
            street=street,
            house_number=address_data["house_number"],
            house_number_addition=address_data.get("house_number_addition", ""),
            place=city
        )

        # Create customer
        customer = Customer.objects.create(
            first_name=customer_data["first_name"],
            second_name=customer_data["second_name"],
            gender=customer_data["gender"],
            birth_date=customer_data["birth_date"],
            title=customer_data.get("title", ""),
            address=address
        )

        # Create contact
        CustomerContact.objects.create(
            customer=customer,
            email=contact_data["email"],
            telephone=contact_data["telephone"]
        )

        return customer
