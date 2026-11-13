from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
    View,
)

from apps.core.permissions import StaffRequiredMixin

from .forms import BookForm, BorrowIssueForm, CategoryForm, ReaderForm
from .models import Book, BorrowRecord, Category, Reader
from .services.borrowing import BorrowingError, issue_book, return_book


# ==============================================================================
# Category Views
# ==============================================================================

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    context_object_name = 'categories'
    template_name = 'library/category_list.html'


class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    context_object_name = 'category'
    template_name = 'library/category_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['books'] = self.object.books.select_related('category').all()
        return context


class CategoryCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library/category_form.html'
    success_url = reverse_lazy('library:category-list')
    success_message = "Category '%(name)s' was created successfully."


class CategoryUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library/category_form.html'
    success_url = reverse_lazy('library:category-list')
    success_message = "Category '%(name)s' was updated successfully."


class CategoryDeleteView(StaffRequiredMixin, DeleteView):
    model = Category
    context_object_name = 'category'
    template_name = 'library/category_confirm_delete.html'
    success_url = reverse_lazy('library:category-list')

    def form_valid(self, form):
        category_name = self.object.name
        try:
            response = super().form_valid(form)
            messages.success(self.request, f"Category '{category_name}' was deleted successfully.")
            return response
        except ProtectedError:
            book_count = self.object.books.count()
            messages.error(
                self.request,
                f"Cannot delete category '{self.object.name}' because it contains {book_count} associated "
                f"book{'s' if book_count != 1 else ''}. Please reassign or delete the books first."
            )
            return redirect('library:category-detail', pk=self.object.pk)


# ==============================================================================
# Book Views
# ==============================================================================

class BookListView(LoginRequiredMixin, ListView):
    """
    Display a paginated, searchable, filterable, and sortable list of books.
    Uses select_related to eliminate N+1 queries for associated categories.
    """
    model = Book
    context_object_name = 'books'
    template_name = 'library/book_list.html'
    paginate_by = 10

    # Whitelist of permitted sort parameters and their corresponding ORM ordering
    SORT_CHOICES = {
        'newest': ('Newest First', ['-created_at', '-id']),
        'oldest': ('Oldest First', ['created_at', 'id']),
        'title_asc': ('Title (A–Z)', ['title', 'author']),
        'title_desc': ('Title (Z–A)', ['-title', 'author']),
        'author_asc': ('Author (A–Z)', ['author', 'title']),
    }
    DEFAULT_SORT = 'newest'

    def get_queryset(self):
        queryset = Book.objects.select_related('category').all()

        # 1. Search (Title, Author, ISBN, Category name)
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            # Guard against excessively long search input (cap at 100 characters)
            search_term = search_query[:100]
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(author__icontains=search_term) |
                Q(isbn__icontains=search_term) |
                Q(category__name__icontains=search_term)
            )

        # 2. Category filtering
        category_param = self.request.GET.get('category', '').strip()
        if category_param:
            try:
                category_id = int(category_param)
                queryset = queryset.filter(category_id=category_id)
            except (ValueError, TypeError):
                # Gracefully ignore invalid or non-numeric category IDs
                pass

        # 3. Availability filtering
        availability_param = self.request.GET.get('availability', '').strip().lower()
        if availability_param == 'available':
            queryset = queryset.filter(available_copies__gt=0)
        elif availability_param == 'unavailable':
            queryset = queryset.filter(available_copies=0)

        # 4. Sorting via strict allowlist
        sort_param = self.request.GET.get('sort', '').strip().lower()
        ordering = self.SORT_CHOICES.get(sort_param, self.SORT_CHOICES[self.DEFAULT_SORT])[1]
        queryset = queryset.order_by(*ordering)

        return queryset

    def paginate_queryset(self, queryset, page_size):
        """
        Handle invalid and out-of-range page numbers gracefully using Paginator.get_page().
        Non-integers return page 1, while numbers > max pages return the last page.
        """
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        page_obj = paginator.get_page(page)
        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pass all categories for the category filter dropdown
        context['categories'] = Category.objects.all().order_by('name')

        # Current search input
        search_query = self.request.GET.get('q', '').strip()[:100]
        context['search_query'] = search_query

        # Current selected category
        selected_category = self.request.GET.get('category', '').strip()
        try:
            context['selected_category'] = int(selected_category) if selected_category else ''
        except (ValueError, TypeError):
            context['selected_category'] = ''

        # Current selected availability
        availability_param = self.request.GET.get('availability', '').strip().lower()
        context['selected_availability'] = (
            availability_param if availability_param in ('available', 'unavailable') else ''
        )

        # Current selected sort
        sort_param = self.request.GET.get('sort', '').strip().lower()
        context['selected_sort'] = sort_param if sort_param in self.SORT_CHOICES else self.DEFAULT_SORT
        context['sort_options'] = [
            (key, val[0]) for key, val in self.SORT_CHOICES.items()
        ]

        # Build querystring without 'page' so pagination preserves filters
        get_params = self.request.GET.copy()
        get_params.pop(self.page_kwarg, None)
        context['querystring'] = get_params.urlencode()

        # Flag indicating whether any filter or search is active
        context['is_filtered'] = bool(
            search_query or
            context['selected_category'] or
            context['selected_availability'] or
            (sort_param and sort_param != self.DEFAULT_SORT)
        )

        return context


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    context_object_name = 'book'
    template_name = 'library/book_detail.html'

    def get_queryset(self):
        return Book.objects.select_related('category')


class BookCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('library:book-list')
    success_message = "Book '%(title)s' was added successfully."


class BookUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('library:book-list')
    success_message = "Book '%(title)s' was updated successfully."


class BookDeleteView(StaffRequiredMixin, DeleteView):
    model = Book
    context_object_name = 'book'
    template_name = 'library/book_confirm_delete.html'
    success_url = reverse_lazy('library:book-list')

    def form_valid(self, form):
        book_title = self.object.title
        response = super().form_valid(form)
        messages.success(self.request, f"Book '{book_title}' was deleted successfully.")
        return response


# ==============================================================================
# Reader Views
# ==============================================================================

class ReaderListView(LoginRequiredMixin, ListView):
    model = Reader
    context_object_name = 'readers'
    template_name = 'library/reader_list.html'


class ReaderDetailView(LoginRequiredMixin, DetailView):
    model = Reader
    context_object_name = 'reader'
    template_name = 'library/reader_detail.html'


class ReaderCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Reader
    form_class = ReaderForm
    template_name = 'library/reader_form.html'
    success_url = reverse_lazy('library:reader-list')
    success_message = "Reader '%(full_name)s' was registered successfully."


class ReaderUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Reader
    form_class = ReaderForm
    template_name = 'library/reader_form.html'
    success_url = reverse_lazy('library:reader-list')
    success_message = "Reader '%(full_name)s' was updated successfully."


class ReaderDeleteView(StaffRequiredMixin, DeleteView):
    model = Reader
    context_object_name = 'reader'
    template_name = 'library/reader_confirm_delete.html'
    success_url = reverse_lazy('library:reader-list')

    def form_valid(self, form):
        reader_name = self.object.full_name
        response = super().form_valid(form)
        messages.success(self.request, f"Reader '{reader_name}' was removed successfully.")
        return response


# ==============================================================================
# Borrowing and Circulation Views
# ==============================================================================

class BorrowRecordListView(LoginRequiredMixin, ListView):
    """
    Circulation management dashboard: Lists borrowing records with tabs for
    All, Active, Returned, and Overdue loans, along with search and pagination.
    """
    model = BorrowRecord
    context_object_name = "borrow_records"
    template_name = "library/borrow_list.html"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            BorrowRecord.objects.select_related("book", "reader", "book__category")
            .all()
        )

        # 1. Filter by operational status
        status_param = (
            self.kwargs.get("default_status")
            or self.request.GET.get("status", "all")
        ).lower()

        if status_param == "active":
            queryset = queryset.filter(status=BorrowRecord.STATUS_ACTIVE)
        elif status_param == "returned":
            queryset = queryset.filter(status=BorrowRecord.STATUS_RETURNED)
        elif status_param == "overdue":
            queryset = queryset.filter(
                status=BorrowRecord.STATUS_ACTIVE,
                due_date__lt=timezone.localdate(),
            )

        # 2. Text Search (reader name, email, book title, ISBN)
        search_query = self.request.GET.get("q", "").strip()[:100]
        if search_query:
            queryset = queryset.filter(
                Q(reader__full_name__icontains=search_query)
                | Q(reader__email__icontains=search_query)
                | Q(book__title__icontains=search_query)
                | Q(book__isbn__icontains=search_query)
            )

        return queryset.order_by("-issue_date", "-id")

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        page_obj = paginator.get_page(page)
        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_param = (
            self.kwargs.get("default_status")
            or self.request.GET.get("status", "all")
        ).lower()
        if status_param not in ("all", "active", "returned", "overdue"):
            status_param = "all"
        context["current_status"] = status_param

        search_query = self.request.GET.get("q", "").strip()[:100]
        context["search_query"] = search_query

        # Summary tab counts
        context["count_all"] = BorrowRecord.objects.count()
        context["count_active"] = BorrowRecord.objects.filter(
            status=BorrowRecord.STATUS_ACTIVE
        ).count()
        context["count_returned"] = BorrowRecord.objects.filter(
            status=BorrowRecord.STATUS_RETURNED
        ).count()
        context["count_overdue"] = BorrowRecord.objects.filter(
            status=BorrowRecord.STATUS_ACTIVE,
            due_date__lt=timezone.localdate(),
        ).count()

        # Build preserved querystring for pagination
        get_params = self.request.GET.copy()
        get_params.pop(self.page_kwarg, None)
        context["querystring"] = get_params.urlencode()

        context["is_filtered"] = bool(search_query or status_param != "all")
        return context


class BorrowRecordDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a single borrow record displaying loan details,
    reader patron information, book inventory status, and return action.
    """
    model = BorrowRecord
    context_object_name = "record"
    template_name = "library/borrow_detail.html"

    def get_queryset(self):
        return BorrowRecord.objects.select_related(
            "book", "reader", "book__category"
        )


class BorrowRecordIssueView(StaffRequiredMixin, FormView):
    """
    Form view for issuing an available book to a registered reader.
    Delegates inventory decrement and concurrency locking to issue_book() service.
    """
    template_name = "library/borrow_form.html"
    form_class = BorrowIssueForm

    def form_valid(self, form):
        reader = form.cleaned_data["reader"]
        book = form.cleaned_data["book"]
        due_date = form.cleaned_data["due_date"]

        try:
            record = issue_book(
                book=book,
                reader=reader,
                due_date=due_date,
            )
            messages.success(
                self.request,
                f"Book '{record.book.title}' was successfully issued to "
                f"{record.reader.full_name} (Due: {record.due_date.strftime('%b %d, %Y')})."
            )
            return redirect("library:borrow-detail", pk=record.pk)
        except BorrowingError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)


class BorrowRecordReturnView(StaffRequiredMixin, View):
    """
    View handling return confirmation (GET) and return execution (POST).
    Restores book inventory and marks borrow record as RETURNED.
    """
    def get(self, request, pk):
        record = get_object_or_404(
            BorrowRecord.objects.select_related("book", "reader"), pk=pk
        )
        if record.status == BorrowRecord.STATUS_RETURNED:
            messages.info(
                request,
                f"Book '{record.book.title}' has already been returned on "
                f"{record.returned_at.strftime('%b %d, %Y')}."
            )
            return redirect("library:borrow-detail", pk=pk)
        return render(request, "library/borrow_confirm_return.html", {"record": record})

    def post(self, request, pk):
        try:
            record = return_book(borrow_record_id=pk)
            messages.success(
                request,
                f"Book '{record.book.title}' was successfully returned by "
                f"{record.reader.full_name}. Inventory restored."
            )
            return redirect("library:borrow-detail", pk=pk)
        except BorrowingError as e:
            messages.error(request, str(e))
            return redirect("library:borrow-detail", pk=pk)

