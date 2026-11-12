from django.shortcuts import render
from django.http import HttpRequest, HttpResponse


def home_view(request: HttpRequest) -> HttpResponse:
    """
    Renders the BookNest home page with introductory context.
    """
    context = {
        'page_title': 'Welcome to BookNest',
        'system_status': 'Operational',
        'current_phase': 'Phase 02 — Project Foundation',
    }
    return render(request, 'core/home.html', context)
