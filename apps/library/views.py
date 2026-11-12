from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import ProtectedError
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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            category_name = self.object.name
            response = super().delete(request, *args, **kwargs)
            messages.success(request, f"Category '{category_name}' was deleted successfully.")
            return response
        except ProtectedError:
            book_count = self.object.books.count()
            messages.error(
                request,
                f"Cannot delete category '{self.object.name}' because it contains {book_count} associated "
                f"book{'s' if book_count != 1 else ''}. Please reassign or delete the books first."
            )
            return redirect('library:category-detail', pk=self.object.pk)


# ==============================================================================
# Book Views
# ==============================================================================

class BookListView(ListView):
    model = Book
    context_object_name = 'books'
    template_name = 'library/book_list.html'

    def get_queryset(self):
        return Book.objects.select_related('category').all()


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


class BookDeleteView(SuccessMessageMixin, DeleteView):
    model = Book
    context_object_name = 'book'
    template_name = 'library/book_confirm_delete.html'
    success_url = reverse_lazy('library:book-list')
    success_message = "Book was deleted successfully."

    def post(self, request, *args, **kwargs):
        messages.success(request, self.success_message)
        return super().post(request, *args, **kwargs)


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


class ReaderDeleteView(SuccessMessageMixin, DeleteView):
    model = Reader
    context_object_name = 'reader'
    template_name = 'library/reader_confirm_delete.html'
    success_url = reverse_lazy('library:reader-list')
    success_message = "Reader was removed successfully."

    def post(self, request, *args, **kwargs):
        messages.success(request, self.success_message)
        return super().post(request, *args, **kwargs)
