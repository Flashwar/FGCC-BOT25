from datetime import date

import plotly.graph_objs as go
from Bot.services import CustomerService
from injector import inject, singleton

@singleton
class Statistics:

    @inject
    def __init__(self, customer_service: CustomerService):
        self.customer_service = customer_service

    # Creates a pie chart using given labels and values
    def create_pie_chart(self, labels, values, title):
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, textinfo='label+value+percent')])
        fig.update_layout(title=title)
        return fig

    # Creates a bar chart using given X and Y values
    def create_bar_chart(self, x, y, title, xaxis_title, yaxis_title):
        fig = go.Figure(data=[go.Bar(x=x, y=y, text=y, textposition='auto')])
        fig.update_layout(title=title, xaxis_title=xaxis_title, yaxis_title=yaxis_title)
        return fig

    # Returns the total number of customers
    def get_total_customers(self) -> int:
        return self.customer_service.get_total_count()

    # Creates an academic titles pie chart
    def get_title_chart(self):
        data = self.customer_service.get_title_distribution()
        labels = [item['title'] or 'Kein Titel' for item in data]
        values = [item['count'] for item in data]
        return self.create_pie_chart(labels, values, 'Titelverteilung')

    # Creates an gender pie chart
    def get_gender_chart(self):
        data = self.customer_service.get_gender_distribution()
        labels = [item['gender'] or 'Unbekannt' for item in data]
        values = [item['count'] for item in data]
        return self.create_pie_chart(labels, values, 'Geschlechterverteilung')

    # Creates a bar chart showing the number of customers per country
    def get_country_chart(self):
        data = self.customer_service.get_country_distribution()
        labels = [item['address__place__country__country_name'] or 'Unbekannt' for item in data]
        values = [item['count'] for item in data]
        return self.create_bar_chart(labels, values, 'Kunden pro Land', 'Land', 'Anzahl')

    # Creates an age distribution pie chart
    def get_age_chart(self):
        age_ranges = {'18–30': 0, '31–50': 0, '51+': 0}
        today = date.today()
        customers = self.customer_service.get_customers_with_birth_dates()

        for customer in customers:
            age = customer.calculate_age()
            if 18 <= age <= 30:
                age_ranges['18–30'] += 1
            elif 31 <= age <= 50:
                age_ranges['31–50'] += 1
            elif age > 50:
                age_ranges['51+'] += 1

        labels = list(age_ranges.keys())
        values = list(age_ranges.values())
        return self.create_pie_chart(labels, values, 'Altersverteilung')
