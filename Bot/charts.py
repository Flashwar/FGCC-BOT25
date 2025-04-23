from django.db.models import Count
from django.shortcuts import render
from plotly.offline import plot
import plotly.graph_objs as go
from .models import Customer


def create_pie_chart(labels, values, title):
    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    fig.update_layout(title=title)
    return fig


def create_bar_chart(x, y, title, xaxis_title, yaxis_title):
    fig = go.Figure(data=[go.Bar(x=x, y=y)])
    fig.update_layout(title=title, xaxis_title=xaxis_title, yaxis_title=yaxis_title)
    return fig


def get_title_chart():
    data = Customer.objects.values('title').annotate(count=Count('title'))
    labels = [item['title'] or 'Kein Titel' for item in data]
    values = [item['count'] for item in data]
    return create_pie_chart(labels, values, 'Titelverteilung')


def get_gender_chart():
    data = Customer.objects.values('gender').annotate(count=Count('gender'))
    labels = [item['gender'] for item in data]
    values = [item['count'] for item in data]
    return create_pie_chart(labels, values, 'Geschlechterverteilung')


def get_country_chart():
    data = Customer.objects.values('address__place__country__country_name').annotate(count=Count('customer_id'))
    labels = [item['address__place__country__country_name'] for item in data]
    values = [item['count'] for item in data]
    return create_bar_chart(labels, values, 'Kunden pro Land', 'Land', 'Anzahl')


def get_age_chart():
    age_ranges = {'18–30': 0, '31–50': 0, '51+': 0}
    customers = Customer.objects.select_related('birthdate')
    for c in customers:
        age = c.calculate_age()
        if 18 <= age <= 30:
            age_ranges['18–30'] += 1
        elif 31 <= age <= 50:
            age_ranges['31–50'] += 1
        else:
            age_ranges['51+'] += 1
    labels = list(age_ranges.keys())
    values = list(age_ranges.values())
    return create_pie_chart(labels, values, 'Altersverteilung')


def customer_stats(request):
    total_customers = Customer.objects.count()

    # Titel
    title_fig = get_title_chart()
    title_chart = plot(title_fig, output_type='div', include_plotlyjs=False)
    request.session['title_fig'] = title_fig.to_json()

    # Geschlecht
    gender_fig = get_gender_chart()
    gender_chart = plot(gender_fig, output_type='div', include_plotlyjs=False)
    request.session['gender_fig'] = gender_fig.to_json()

    # Land
    country_fig = get_country_chart()
    country_chart = plot(country_fig, output_type='div', include_plotlyjs=False)
    request.session['country_fig'] = country_fig.to_json()

    # Alter
    age_fig = get_age_chart()
    age_chart = plot(age_fig, output_type='div', include_plotlyjs=False)
    request.session['age_fig'] = age_fig.to_json()

    return render(request, 'statistics.html', {
        'total_customers': total_customers,
        'title_chart': title_chart,
        'gender_chart': gender_chart,
        'country_chart': country_chart,
        'age_chart': age_chart
    })
