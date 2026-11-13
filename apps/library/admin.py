from django.contrib import admin
from .models import Book, BorrowRecord, Category, Reader


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'category', 'isbn',
        'available_copies', 'total_copies', 'created_at'
    ]
    list_filter = ['category', 'publication_date']
    search_fields = ['title', 'author', 'isbn']
    ordering = ['title']


@admin.register(Reader)
class ReaderAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'created_at']
    search_fields = ['full_name', 'email', 'phone']
    ordering = ['full_name']


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    """
    Admin configuration for BorrowRecord.
    Strictly read-only for add, change, and delete to prevent administrators
    from bypassing circulation service functions and corrupting book inventory.
    """
    list_display = [
        'book', 'reader', 'issue_date', 'due_date',
        'returned_at', 'status', 'is_overdue_display'
    ]
    list_filter = ['status', 'issue_date', 'due_date']
    search_fields = [
        'book__title', 'book__isbn', 'reader__full_name', 'reader__email'
    ]
    readonly_fields = [
        'book', 'reader', 'issue_date', 'due_date',
        'returned_at', 'status', 'created_at', 'updated_at'
    ]
    ordering = ['-issue_date', '-id']

    def has_add_permission(self, request):
        # Disallow direct creation via admin (must use issue_book service/UI)
        return False

    def has_change_permission(self, request, obj=None):
        # Disallow direct edits via admin (must use return_book service/UI)
        return False

    def has_delete_permission(self, request, obj=None):
        # Disallow deleting loan history to preserve audit integrity
        return False

    @admin.display(boolean=True, description='Overdue')
    def is_overdue_display(self, obj):
        return obj.is_overdue
