from injector import singleton
from django.db.models import Count
from django.db import transaction
from asgiref.sync import sync_to_async
from Bot.models import Customer, AddressCountry, AddressStreet, AddressCity, Address, CustomerContact

@singleton
class CustomerService:
    # Service for handling all customer-related database operations

    def get_all_customers_with_relations(self):
        # Retrieve all customers with their associated address, street, city, and country
        # Uses select_related for performance optimization
        return Customer.objects.select_related(
            'address__street',
            'address__place__country'
        ).all()

    def get_total_count(self):
        # Get total number of customer records in the database
        return Customer.objects.count()

    def get_title_distribution(self):
        # Return a list of customer titles with their corresponding count
        return list(Customer.objects.values('title').annotate(count=Count('title')))

    def get_gender_distribution(self):
        # Return a list of customer genders with their corresponding count
        return list(Customer.objects.values('gender').annotate(count=Count('gender')))

    def get_country_distribution(self):
        # Return a list showing how many customers are from each country
        return list(
            Customer.objects
            .values('address__place__country__country_name')
            .annotate(count=Count('customer_id'))
        )

    def get_customers_with_birth_dates(self):
        # Retrieve all customers with a birth_date
        # Return only required fields: customer_id and birth_date
        return Customer.objects.exclude(birth_date__isnull=True).only('customer_id', 'birth_date')

    async def email_exists_in_db(self, email: str) -> bool:
        # Check whether the given email exists in the customer contact table

        def _check_email():
            return CustomerContact.objects.filter(email=email).exists()

        return await sync_to_async(_check_email, thread_sensitive=False)()

    async def store_data_db(self, user_profile: dict) -> bool:
        # Save customer data into the database based on a user profile dictionary
        def _store_data_sync():
            # synchron helper function to execute database operations within a transaction
            try:
                with transaction.atomic():
                    # Create or retrieve country
                    country_obj, _ = AddressCountry.objects.get_or_create(
                        country_name=user_profile['country_name']
                    )

                    # Create or retrieve street
                    street_obj, _ = AddressStreet.objects.get_or_create(
                        street_name=user_profile['street_name']
                    )

                    # Create or retrieve city
                    city_obj, _ = AddressCity.objects.get_or_create(
                        city=user_profile['city'],
                        postal_code=user_profile['postal_code'],
                        country=country_obj
                    )

                    # Create address
                    address_obj = Address.objects.create(
                        street=street_obj,
                        house_number=user_profile['house_number'],
                        house_number_addition=user_profile.get('house_number_addition', ''),
                        place=city_obj
                    )

                    # Create customer
                    customer = Customer.objects.create(
                        gender=user_profile['gender'],
                        first_name=user_profile['first_name'],
                        second_name=user_profile['last_name'],
                        birth_date=user_profile['birth_date'],
                        title=user_profile.get('title', ''),
                        address=address_obj
                    )

                    # Create customer contact
                    CustomerContact.objects.create(
                        customer=customer,
                        email=user_profile['email'],
                        telephone=user_profile['telephone']
                    )

                    return True

            except Exception as e:
                print(f"Error while saving customer data {e}")
                return False

        # Run the sync operation asynchronously
        return await sync_to_async(_store_data_sync, thread_sensitive=False)()