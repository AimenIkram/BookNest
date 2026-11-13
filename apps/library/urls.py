from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),

    # Book URLs
    path('books/', views.BookListView.as_view(), name='book-list'),
    path('books/add/', views.BookCreateView.as_view(), name='book-create'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book-detail'),
    path('books/<int:pk>/edit/', views.BookUpdateView.as_view(), name='book-update'),
    path('books/<int:pk>/delete/', views.BookDeleteView.as_view(), name='book-delete'),

    # Reader URLs
    path('readers/', views.ReaderListView.as_view(), name='reader-list'),
    path('readers/add/', views.ReaderCreateView.as_view(), name='reader-create'),
    path('readers/<int:pk>/', views.ReaderDetailView.as_view(), name='reader-detail'),
    path('readers/<int:pk>/edit/', views.ReaderUpdateView.as_view(), name='reader-update'),
    path('readers/<int:pk>/delete/', views.ReaderDeleteView.as_view(), name='reader-delete'),

    # Borrowing & Circulation URLs
    path('borrow/', views.BorrowRecordListView.as_view(), name='borrow-list'),
    path('borrow/active/', views.BorrowRecordListView.as_view(), {'default_status': 'active'}, name='borrow-active'),
    path('borrow/returned/', views.BorrowRecordListView.as_view(), {'default_status': 'returned'}, name='borrow-returned'),
    path('borrow/overdue/', views.BorrowRecordListView.as_view(), {'default_status': 'overdue'}, name='borrow-overdue'),
    path('borrow/issue/', views.BorrowRecordIssueView.as_view(), name='borrow-issue'),
    path('borrow/<int:pk>/', views.BorrowRecordDetailView.as_view(), name='borrow-detail'),
    path('borrow/<int:pk>/return/', views.BorrowRecordReturnView.as_view(), name='borrow-return'),
]
