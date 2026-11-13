from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.core.forms import BookNestLoginForm
from apps.library.models import Book, BorrowRecord, Category, Reader


class BookNestLoginView(LoginView):
    """
    Standard session-based login view using Django's built-in authentication framework.
    Redirects authenticated users to the dashboard upon successful login.
    """
    template_name = "core/login.html"
    form_class = BookNestLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        messages.success(
            self.request,
            f"Welcome back, {user.get_full_name() or user.username}!"
        )
        return super().form_valid(form)


class BookNestLogoutView(LogoutView):
    """
    CSRF-protected POST logout view using Django's built-in authentication framework.
    Clears session and redirects user to the login page with an informative message.
    """
    next_page = reverse_lazy("core:login")

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have been logged out successfully.")
        return response


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    """
    Administrative Dashboard for BookNest.
    Aggregates live database statistics, recent circulation activity,
    overdue alerts, and inventory health metrics.
    Protected: Requires user authentication.
    """
    today = timezone.localdate()

    # 1. Core Entity Counts
    total_books = Book.objects.count()
    total_categories = Category.objects.count()
    total_readers = Reader.objects.count()

    # 2. Inventory Aggregation (single query)
    inventory_totals = Book.objects.aggregate(
        total_copies=Sum("total_copies"),
        available_copies=Sum("available_copies"),
    )
    total_copies = inventory_totals["total_copies"] or 0
    available_copies = inventory_totals["available_copies"] or 0
    borrowed_copies = max(0, total_copies - available_copies)
    inventory_utilization = (
        round((borrowed_copies / total_copies) * 100, 1) if total_copies > 0 else 0
    )

    # 3. Circulation & Loan Statistics
    active_borrows = BorrowRecord.objects.filter(
        status=BorrowRecord.STATUS_ACTIVE
    ).count()
    returned_borrows = BorrowRecord.objects.filter(
        status=BorrowRecord.STATUS_RETURNED
    ).count()
    overdue_borrows = BorrowRecord.objects.filter(
        status=BorrowRecord.STATUS_ACTIVE,
        due_date__lt=today,
    ).count()

    # 4. Recent Borrowing Activity (latest 5 issued or returned)
    recent_activity = (
        BorrowRecord.objects.select_related("book", "reader", "book__category")
        .order_by("-updated_at", "-id")[:5]
    )

    # 5. Overdue Books (up to 5 most urgent)
    overdue_records = (
        BorrowRecord.objects.filter(
            status=BorrowRecord.STATUS_ACTIVE,
            due_date__lt=today,
        )
        .select_related("book", "reader", "book__category")
        .order_by("due_date")[:5]
    )

    # 6. Low or Zero Availability Inventory (copies <= 1 or depleted)
    low_inventory_books = (
        Book.objects.filter(available_copies__lte=1)
        .select_related("category")
        .order_by("available_copies", "title")[:5]
    )

    context = {
        "page_title": "Administrative Dashboard",
        "system_status": "Operational",
        "current_phase": "Phase 10 — Authentication and Permissions",
        "today": today,
        # Statistics
        "total_books": total_books,
        "total_categories": total_categories,
        "total_readers": total_readers,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "borrowed_copies": borrowed_copies,
        "inventory_utilization": inventory_utilization,
        "active_borrows": active_borrows,
        "returned_borrows": returned_borrows,
        "overdue_borrows": overdue_borrows,
        # Activity & Alerts
        "recent_activity": recent_activity,
        "overdue_records": overdue_records,
        "low_inventory_books": low_inventory_books,
    }
    return render(request, "core/home.html", context)
