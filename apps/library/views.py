from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import BookForm, CategoryForm, ReaderForm
from .models import Book, Category, Reader


# ==============================================================================
# Category Views
# ==============================================================================

class CategoryListView(ListView):
    model = Category
    context_object_name = 'categories'
    template_name = 'library/category_list.html'


class CategoryDetailView(DetailView):
    model = Category
    context_object_name = 'category'
    template_name = 'library/category_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['books'] = self.object.books.select_related('category').all()
        return context


class CategoryCreateView(SuccessMessageMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library/category_form.html'
    success_url = reverse_lazy('library:category-list')
    success_message = "Category '%(name)s' was created successfully."


class CategoryUpdateView(SuccessMessageMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library/category_form.html'
    success_url = reverse_lazy('library:category-list')
    success_message = "Category '%(name)s' was updated successfully."


class CategoryDeleteView(DeleteView):
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

class BookListView(ListView):
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


class BookDetailView(DetailView):
    model = Book
    context_object_name = 'book'
    template_name = 'library/book_detail.html'

    def get_queryset(self):
        return Book.objects.select_related('category')


class BookCreateView(SuccessMessageMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('library:book-list')
    success_message = "Book '%(title)s' was added successfully."


class BookUpdateView(SuccessMessageMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('library:book-list')
    success_message = "Book '%(title)s' was updated successfully."


class BookDeleteView(DeleteView):
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

class ReaderListView(ListView):
    model = Reader
    context_object_name = 'readers'
    template_name = 'library/reader_list.html'


class ReaderDetailView(DetailView):
    model = Reader
    context_object_name = 'reader'
    template_name = 'library/reader_detail.html'


class ReaderCreateView(SuccessMessageMixin, CreateView):
    model = Reader
    form_class = ReaderForm
    template_name = 'library/reader_form.html'
    success_url = reverse_lazy('library:reader-list')
    success_message = "Reader '%(full_name)s' was registered successfully."


class ReaderUpdateView(SuccessMessageMixin, UpdateView):
    model = Reader
    form_class = ReaderForm
    template_name = 'library/reader_form.html'
    success_url = reverse_lazy('library:reader-list')
    success_message = "Reader '%(full_name)s' was updated successfully."


class ReaderDeleteView(DeleteView):
    model = Reader
    context_object_name = 'reader'
    template_name = 'library/reader_confirm_delete.html'
    success_url = reverse_lazy('library:reader-list')

    def form_valid(self, form):
        reader_name = self.object.full_name
        response = super().form_valid(form)
        messages.success(self.request, f"Reader '{reader_name}' was removed successfully.")
        return response
