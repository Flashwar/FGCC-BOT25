from allauth.account.views import LoginView
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django_tables2 import RequestConfig
from django_tables2.export import TableExport

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