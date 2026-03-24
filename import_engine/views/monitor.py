import os
from django.views import View
from django.views.generic import TemplateView
from django.http import HttpResponse, Http404
from django.conf import settings

class TestReportListView(TemplateView):
    """
    Premium Django HTML Monitor - List View.
    Provides a high-end Glassmorphism interface for browsing ALL 100K+ diagnostic reports.
    """
    template_name = "import_engine/report_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_dir = os.path.join(settings.BASE_DIR, "import_engine/static/reports")
        reports = []
        if os.path.exists(report_dir):
            reports = [f for f in os.listdir(report_dir) if f.endswith(".html")]
        
        context["reports"] = sorted(reports, reverse=True)
        return context

class TestReportDetailView(View):
    """
    Premium Django HTML Monitor - Detail View.
    Directly renders the high-fidelity diagnostic dashboard for a specific test run.
    """
    def get(self, request, report_name):
        report_path = os.path.join(settings.BASE_DIR, "import_engine/static/reports", report_name)
        if not os.path.exists(report_path):
            raise Http404("Diagnostic report not found.")
            
        with open(report_path, "r") as f:
            return HttpResponse(f.read(), content_type="text/html")
