import base64
import io
from allauth.account.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse, FileResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django_tables2 import RequestConfig
from django_tables2.export import TableExport
from plotly.offline import plot
from django.db.models import Count
from django.shortcuts import render
from weasyprint import HTML

import Bot.charts
from Bot import charts
from Bot.filters import CustomerFilter
from Bot.models import Customer
from Bot.tables import CustomerTable

class SuperuserLoginView(LoginView):
    def form_valid(self, form):
        user = form.user
        if not user.is_superuser:
            messages.error(self.request, "Nur für Superuser.")
            return self.form_invalid(form)
        return super().form_valid(form)


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)


@superuser_required
def admin_dashboard(request):
    queryset = Customer.objects.select_related(
        'birthdate', 'address__street', 'address__place__country'
    ).all()
    f = CustomerFilter(request.GET, queryset=queryset)
    table = CustomerTable(f.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)

    export_format = request.GET.get('_export', None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response(f"CustomerTable.{export_format}")

    return render(request, 'dashboard.html', {'table': table, 'filter': f})


@superuser_required
def customer_stats(request):
    total_customers = Customer.objects.count()

    # Titel
    title_fig = Bot.charts.get_title_chart()
    title_chart = plot(title_fig, output_type='div', include_plotlyjs=False)
    request.session['title_fig'] = title_fig.to_json()

    # Geschlecht
    gender_fig = Bot.charts.get_gender_chart()
    gender_chart = plot(gender_fig, output_type='div', include_plotlyjs=False)
    request.session['gender_fig'] = gender_fig.to_json()

    # Land
    country_fig = Bot.charts.get_country_chart()
    country_chart = plot(country_fig, output_type='div', include_plotlyjs=False)
    request.session['country_fig'] = country_fig.to_json()

    # Alter
    age_fig = Bot.charts.get_age_chart()
    age_chart = plot(age_fig, output_type='div', include_plotlyjs=False)
    request.session['age_fig'] = age_fig.to_json()

    return render(request, 'statistics.html', {
        'total_customers': total_customers,
        'title_chart': title_chart,
        'gender_chart': gender_chart,
        'country_chart': country_chart,
        'age_chart': age_chart
    })


def generate_pdf_from_plotly(fig, title, filename):
    # get the total number of customers
    total_customers = Customer.objects.count()

    # Export Plotly figure to PNG
    img_bytes = io.BytesIO()
    fig.write_image(img_bytes, format='png', width=800, height=500)
    img_bytes.seek(0)

    # Convert PNG to base64 for embedding in HTML
    encoded = base64.b64encode(img_bytes.read()).decode()
    image_uri = f'data:image/png;base64,{encoded}'

    # Render HTML
    html_string = render_to_string('pdf_stats_template.html', {
        'title': title,
        'image_uri': image_uri,
        'total_customers': total_customers
    })

    # Generate PDF
    pdf = HTML(string=html_string).write_pdf()

    return HttpResponse(pdf, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })

def customer_stats_pdf(request, chart_type: str):
    print(chart_type)
    fig = None
    match chart_type:
        case "title":
            fig = charts.get_title_chart()
            return generate_pdf_from_plotly(fig, "Titelverteilung", "titel_statistik.pdf")
        case "gender":
            fig = charts.get_gender_chart()
            return generate_pdf_from_plotly(fig, "Geschlechterverteilung", "geschlecht_statistik.pdf")
        case "country":
            fig = charts.get_country_chart()
            return generate_pdf_from_plotly(fig, "Kunden pro Land", "land_statistik.pdf")
        case "age":
            fig = charts.get_age_chart()
            return generate_pdf_from_plotly(fig, "Altersverteilung", "alters_statistik.pdf")
        case _:
            return HttpResponse("Ungültiger Chart-Typ", status=400)

