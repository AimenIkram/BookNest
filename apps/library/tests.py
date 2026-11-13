import datetime
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.library.forms import BookForm, BorrowIssueForm, CategoryForm, ReaderForm
from apps.library.models import Book, BorrowRecord, Category, Reader
from apps.library.services.borrowing import BorrowingError, issue_book, return_book


# ==============================================================================
# Model Tests (Preserved from Phase 04)
# ==============================================================================

class CategoryModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Science Fiction",
            description="Speculative fiction with futuristic concepts."
        )

    def test_create_category_successful(self):
        self.assertEqual(self.category.name, "Science Fiction")
        self.assertTrue(self.category.description.startswith("Speculative"))
        self.assertIsNotNone(self.category.created_at)
        self.assertIsNotNone(self.category.updated_at)

    def test_category_str_representation(self):
        self.assertEqual(str(self.category), "Science Fiction")

    def test_category_name_uniqueness(self):
        with self.assertRaises(IntegrityError):
            Category.objects.create(
                name="Science Fiction",
                description="Duplicate category attempt."
            )


class BookModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Computer Science",
            description="Books on computing and software."
        )
        self.book = Book.objects.create(
            title="Clean Architecture",
            author="Robert C. Martin",
            isbn="9780134494166",
            description="Software Structure and Design.",
            publication_date=datetime.date(2017, 9, 20),
            category=self.category,
            total_copies=5,
            available_copies=5,
        )

    def test_create_book_successful(self):
        self.assertEqual(self.book.title, "Clean Architecture")
        self.assertEqual(self.book.author, "Robert C. Martin")
        self.assertEqual(self.book.total_copies, 5)
        self.assertEqual(self.book.available_copies, 5)

    def test_book_str_representation(self):
        self.assertEqual(str(self.book), "Clean Architecture by Robert C. Martin")

    def test_book_category_relationship(self):
        self.assertEqual(self.book.category, self.category)
        self.assertIn(self.book, self.category.books.all())

    def test_category_deletion_protection(self):
        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_isbn_uniqueness(self):
        with self.assertRaises(IntegrityError):
            Book.objects.create(
                title="Another Clean Architecture",
                author="Someone Else",
                isbn="9780134494166",
                category=self.category,
                total_copies=2,
                available_copies=2,
            )

    def test_available_copies_cannot_exceed_total_model_validation(self):
        invalid_book = Book(
            title="Invalid Book",
            author="Unknown",
            category=self.category,
            total_copies=2,
            available_copies=5,
        )
        with self.assertRaises(ValidationError):
            invalid_book.full_clean()

    def test_available_copies_cannot_exceed_total_db_constraint(self):
        with self.assertRaises(IntegrityError):
            Book.objects.create(
                title="Constraint Violator",
                author="Author",
                category=self.category,
                total_copies=1,
                available_copies=3,
            )


class ReaderModelTests(TestCase):
    def setUp(self):
        self.reader = Reader.objects.create(
            full_name="Ada Lovelace",
            email="ada@example.com",
            phone="+1234567890",
            address="12 Analytical Engine Way"
        )

    def test_create_reader_successful(self):
        self.assertEqual(self.reader.full_name, "Ada Lovelace")
        self.assertEqual(self.reader.email, "ada@example.com")

    def test_reader_str_representation(self):
        self.assertEqual(str(self.reader), "Ada Lovelace")

    def test_reader_optional_fields(self):
        minimal_reader = Reader.objects.create(full_name="Grace Hopper")
        self.assertEqual(minimal_reader.full_name, "Grace Hopper")
        self.assertIsNone(minimal_reader.email)
        self.assertEqual(minimal_reader.phone, "")

    def test_reader_email_uniqueness(self):
        with self.assertRaises(IntegrityError):
            Reader.objects.create(
                full_name="Impostor Ada",
                email="ada@example.com"
            )


# ==============================================================================
# Phase 06: Form & Validation Unit Tests
# ==============================================================================

class CategoryFormValidationTests(TestCase):
    """
    Tests for CategoryForm field validation, whitespace trimming, and duplicate handling.
    """

    def test_category_form_valid(self):
        form = CategoryForm(data={
            'name': 'Mathematics',
            'description': 'Pure and applied mathematics.',
        })
        self.assertTrue(form.is_valid())
        category = form.save()
        self.assertEqual(category.name, 'Mathematics')

    def test_category_form_missing_name(self):
        form = CategoryForm(data={'name': '', 'description': 'No name'})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_category_form_whitespace_only_name(self):
        form = CategoryForm(data={'name': '   ', 'description': 'Only spaces'})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
        self.assertIn("This field is required.", form.errors['name'])

    def test_category_form_trims_whitespace(self):
        form = CategoryForm(data={'name': '   History   ', 'description': '  World history  '})
        self.assertTrue(form.is_valid())
        category = form.save()
        self.assertEqual(category.name, 'History')
        self.assertEqual(category.description, 'World history')

    def test_category_form_case_insensitive_duplicate(self):
        Category.objects.create(name='Biographies')
        form = CategoryForm(data={'name': 'biographies'})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
        self.assertIn("already exists", form.errors['name'][0])

    def test_category_form_update_own_name_allowed(self):
        cat = Category.objects.create(name='Poetry')
        form = CategoryForm(instance=cat, data={'name': 'Poetry', 'description': 'Updated'})
        self.assertTrue(form.is_valid())


class BookFormValidationTests(TestCase):
    """
    Tests for BookForm validation: ISBN formats, publication dates, and copies balance.
    """

    def setUp(self):
        self.category = Category.objects.create(name="Technology")

    def test_book_form_valid(self):
        form = BookForm(data={
            'title': 'The Pragmatic Programmer',
            'author': 'David Thomas, Andrew Hunt',
            'isbn': '978-0-13-595705-9',
            'category': self.category.pk,
            'total_copies': 10,
            'available_copies': 10,
            'publication_date': '2019-09-13',
            'description': 'Software craftsmanship book.',
        })
        self.assertTrue(form.is_valid(), form.errors)
        book = form.save()
        # ISBN must be normalized (hyphens stripped)
        self.assertEqual(book.isbn, '9780135957059')

    def test_book_form_missing_required_fields(self):
        form = BookForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('author', form.errors)
        self.assertIn('category', form.errors)
        self.assertIn('total_copies', form.errors)
        self.assertIn('available_copies', form.errors)

    def test_book_form_whitespace_trimmed(self):
        form = BookForm(data={
            'title': '   Refactoring   ',
            'author': '   Martin Fowler   ',
            'category': self.category.pk,
            'total_copies': 5,
            'available_copies': 5,
        })
        self.assertTrue(form.is_valid(), form.errors)
        book = form.save()
        self.assertEqual(book.title, 'Refactoring')
        self.assertEqual(book.author, 'Martin Fowler')

    def test_book_form_valid_isbn_10(self):
        form = BookForm(data={
            'title': 'Design Patterns',
            'author': 'GoF',
            'isbn': '0-201-63361-2',
            'category': self.category.pk,
            'total_copies': 3,
            'available_copies': 3,
        })
        self.assertTrue(form.is_valid(), form.errors)
        book = form.save()
        self.assertEqual(book.isbn, '0201633612')

    def test_book_form_valid_isbn_10_with_x(self):
        form = BookForm(data={
            'title': 'Sample Book',
            'author': 'Author',
            'isbn': '080442957X',
            'category': self.category.pk,
            'total_copies': 1,
            'available_copies': 1,
        })
        self.assertTrue(form.is_valid(), form.errors)
        book = form.save()
        self.assertEqual(book.isbn, '080442957X')

    def test_book_form_invalid_isbn_length(self):
        form = BookForm(data={
            'title': 'Bad ISBN Book',
            'author': 'Author',
            'isbn': '12345',  # Too short
            'category': self.category.pk,
            'total_copies': 1,
            'available_copies': 1,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('isbn', form.errors)
        self.assertIn("Invalid ISBN length", form.errors['isbn'][0])

    def test_book_form_invalid_isbn_characters(self):
        form = BookForm(data={
            'title': 'Bad ISBN Book',
            'author': 'Author',
            'isbn': '978-0-13-ABCDEF-0',
            'category': self.category.pk,
            'total_copies': 1,
            'available_copies': 1,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('isbn', form.errors)

    def test_book_form_duplicate_isbn_normalized(self):
        Book.objects.create(
            title="First Book",
            author="Author One",
            isbn="9780134494166",
            category=self.category,
            total_copies=1,
            available_copies=1,
        )
        # Attempt to create book with hyphenated duplicate ISBN
        form = BookForm(data={
            'title': 'Second Book',
            'author': 'Author Two',
            'isbn': '978-0-13-449416-6',
            'category': self.category.pk,
            'total_copies': 1,
            'available_copies': 1,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('isbn', form.errors)
        self.assertIn("already exists", form.errors['isbn'][0])

    def test_book_form_empty_isbn_normalized_to_none(self):
        form = BookForm(data={
            'title': 'No ISBN Book',
            'author': 'Author',
            'isbn': '   ',  # Whitespace only
            'category': self.category.pk,
            'total_copies': 2,
            'available_copies': 2,
        })
        self.assertTrue(form.is_valid(), form.errors)
        book = form.save()
        self.assertIsNone(book.isbn)

    def test_book_form_future_publication_date_rejected(self):
        future_date = datetime.date.today() + datetime.timedelta(days=365)
        form = BookForm(data={
            'title': 'Future Book',
            'author': 'Time Traveler',
            'category': self.category.pk,
            'total_copies': 1,
            'available_copies': 1,
            'publication_date': future_date.strftime('%Y-%m-%d'),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('publication_date', form.errors)
        self.assertIn("cannot be in the future", form.errors['publication_date'][0])

    def test_book_form_negative_copies_rejected(self):
        form = BookForm(data={
            'title': 'Negative Book',
            'author': 'Author',
            'category': self.category.pk,
            'total_copies': -5,
            'available_copies': -2,
        })
        self.assertFalse(form.is_valid())
        self.assertTrue('total_copies' in form.errors or 'available_copies' in form.errors)

    def test_book_form_available_copies_exceeds_total(self):
        form = BookForm(data={
            'title': 'Surplus Book',
            'author': 'Author',
            'category': self.category.pk,
            'total_copies': 2,
            'available_copies': 5,  # Exceeds total
        })
        self.assertFalse(form.is_valid())
        self.assertIn('available_copies', form.errors)
        self.assertIn("cannot exceed total copies", form.errors['available_copies'][0])


class ReaderFormValidationTests(TestCase):
    """
    Tests for ReaderForm validation: full name, email normalization, phone format.
    """

    def test_reader_form_valid(self):
        form = ReaderForm(data={
            'full_name': 'Margaret Hamilton',
            'email': 'margaret@apollo.nasa.gov',
            'phone': '+1 (555) 019-2834',
            'address': 'Cambridge, Massachusetts',
        })
        self.assertTrue(form.is_valid(), form.errors)
        reader = form.save()
        self.assertEqual(reader.full_name, 'Margaret Hamilton')
        self.assertEqual(reader.email, 'margaret@apollo.nasa.gov')
        self.assertEqual(reader.phone, '+1 (555) 019-2834')

    def test_reader_form_missing_name(self):
        form = ReaderForm(data={'full_name': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('full_name', form.errors)

    def test_reader_form_short_name(self):
        form = ReaderForm(data={'full_name': 'A'})
        self.assertFalse(form.is_valid())
        self.assertIn('full_name', form.errors)
        self.assertIn("at least 2 characters", form.errors['full_name'][0])

    def test_reader_form_email_lowercased_and_trimmed(self):
        form = ReaderForm(data={
            'full_name': 'Grace Hopper',
            'email': '  Grace.Hopper@USNAVY.mil  ',
        })
        self.assertTrue(form.is_valid(), form.errors)
        reader = form.save()
        self.assertEqual(reader.email, 'grace.hopper@usnavy.mil')

    def test_reader_form_invalid_email(self):
        form = ReaderForm(data={
            'full_name': 'Test User',
            'email': 'not-an-email',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_reader_form_duplicate_email_case_insensitive(self):
        Reader.objects.create(full_name='Existing Reader', email='patron@library.org')
        form = ReaderForm(data={
            'full_name': 'New Reader',
            'email': 'PATRON@LIBRARY.ORG',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn("already registered", form.errors['email'][0])

    def test_reader_form_empty_email_normalized_to_none(self):
        form = ReaderForm(data={
            'full_name': 'No Email Reader',
            'email': '   ',  # Whitespace only
        })
        self.assertTrue(form.is_valid(), form.errors)
        reader = form.save()
        self.assertIsNone(reader.email)

    def test_reader_form_valid_phone_numbers(self):
        valid_numbers = [
            '+1-555-0199',
            '(555) 019-2834',
            '03001234567',
            '+44 20 7946 0919',
            '555.019.2834',
        ]
        for phone in valid_numbers:
            form = ReaderForm(data={'full_name': 'Test Phone Reader', 'phone': phone})
            self.assertTrue(form.is_valid(), f"Failed on valid phone: {phone}")

    def test_reader_form_invalid_phone_numbers(self):
        invalid_numbers = [
            '12345',         # Too short (< 7 digits)
            '1234567890123456789', # Too long (> 15 digits)
            'call-me-maybe', # Alphabetic
            '+++555---',     # Malformed symbols
        ]
        for phone in invalid_numbers:
            form = ReaderForm(data={'full_name': 'Bad Phone Reader', 'phone': phone})
            self.assertFalse(form.is_valid(), f"Passed on invalid phone: {phone}")
            self.assertIn('phone', form.errors)


# ==============================================================================
# Category CRUD Views Tests (Including Dual GET/POST Coverage)
# ==============================================================================

class CategoryCRUDTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_category",
            password="password123",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.category = Category.objects.create(
            name="Philosophy",
            description="Works of philosophical inquiry."
        )

    def test_category_list_view(self):
        response = self.client.get(reverse('library:category-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/category_list.html')
        self.assertContains(response, "Philosophy")

    def test_category_detail_view(self):
        Book.objects.create(
            title="Meditations",
            author="Marcus Aurelius",
            category=self.category,
            total_copies=3,
            available_copies=3,
        )
        response = self.client.get(reverse('library:category-detail', args=[self.category.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/category_detail.html')
        self.assertContains(response, "Philosophy")
        self.assertContains(response, "Meditations")

    def test_category_create_view_get(self):
        response = self.client.get(reverse('library:category-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/category_form.html')

    def test_category_create_view_valid(self):
        response = self.client.post(reverse('library:category-create'), {
            'name': 'History',
            'description': 'Historical accounts and analyses.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:category-list'))
        self.assertTrue(Category.objects.filter(name='History').exists())

    def test_category_create_view_invalid(self):
        response = self.client.post(reverse('library:category-create'), {
            'name': '',
            'description': 'Missing name',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'name', 'This field is required.')

    def test_category_update_view_get(self):
        response = self.client.get(reverse('library:category-update', args=[self.category.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/category_form.html')

    def test_category_update_view_post(self):
        response = self.client.post(reverse('library:category-update', args=[self.category.pk]), {
            'name': 'Modern Philosophy',
            'description': 'Updated description.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:category-list'))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Modern Philosophy')

    def test_category_delete_view_get_confirm_page(self):
        response = self.client.get(reverse('library:category-delete', args=[self.category.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/category_confirm_delete.html')

    def test_category_delete_without_books_succeeds(self):
        empty_category = Category.objects.create(name='Disposable')
        response = self.client.post(reverse('library:category-delete', args=[empty_category.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:category-list'))
        self.assertFalse(Category.objects.filter(pk=empty_category.pk).exists())

    def test_category_delete_with_books_handles_protected_error(self):
        Book.objects.create(
            title="Beyond Good and Evil",
            author="Friedrich Nietzsche",
            category=self.category,
            total_copies=2,
            available_copies=2,
        )
        response = self.client.post(
            reverse('library:category-delete', args=[self.category.pk]),
            follow=True
        )
        self.assertRedirects(response, reverse('library:category-detail', args=[self.category.pk]))
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        messages = list(response.context['messages'])
        self.assertTrue(any("Cannot delete category" in str(m) for m in messages))


# ==============================================================================
# Book CRUD Views Tests (Including Dual GET/POST Coverage)
# ==============================================================================

class BookCRUDTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_book",
            password="password123",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.category = Category.objects.create(name="Fiction")
        self.book = Book.objects.create(
            title="The Hobbit",
            author="J.R.R. Tolkien",
            isbn="9780547928227",
            category=self.category,
            total_copies=4,
            available_copies=4,
            description="Fantasy novel.",
        )

    def test_book_list_view(self):
        response = self.client.get(reverse('library:book-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book_list.html')
        self.assertContains(response, "The Hobbit")

    def test_book_detail_view(self):
        response = self.client.get(reverse('library:book-detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book_detail.html')
        self.assertContains(response, "The Hobbit")
        self.assertContains(response, "J.R.R. Tolkien")

    def test_book_create_view_get(self):
        response = self.client.get(reverse('library:book-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book_form.html')

    def test_book_create_view_valid(self):
        response = self.client.post(reverse('library:book-create'), {
            'title': '1984',
            'author': 'George Orwell',
            'isbn': '978-0-451-52493-5',  # Normalized to 9780451524935
            'category': self.category.pk,
            'total_copies': 6,
            'available_copies': 6,
            'publication_date': '1949-06-08',
            'description': 'Dystopian classic.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:book-list'))
        book = Book.objects.get(title='1984')
        self.assertEqual(book.isbn, '9780451524935')

    def test_book_create_view_invalid_copies(self):
        response = self.client.post(reverse('library:book-create'), {
            'title': 'Invalid Book',
            'author': 'Test Author',
            'category': self.category.pk,
            'total_copies': 2,
            'available_copies': 5,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'available_copies',
            "Available copies cannot exceed total copies."
        )

    def test_book_update_view_get(self):
        response = self.client.get(reverse('library:book-update', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book_form.html')

    def test_book_update_view_post(self):
        response = self.client.post(reverse('library:book-update', args=[self.book.pk]), {
            'title': 'The Hobbit: Illustrated Edition',
            'author': 'J.R.R. Tolkien',
            'isbn': '978-0-547-92822-7',
            'category': self.category.pk,
            'total_copies': 10,
            'available_copies': 8,
            'description': 'Updated description.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:book-list'))
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'The Hobbit: Illustrated Edition')
        self.assertEqual(self.book.total_copies, 10)
        self.assertEqual(self.book.available_copies, 8)

    def test_book_delete_view_get_confirm_page(self):
        response = self.client.get(reverse('library:book-delete', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/book_confirm_delete.html')

    def test_book_delete_view_post(self):
        response = self.client.post(reverse('library:book-delete', args=[self.book.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:book-list'))
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())


# ==============================================================================
# Reader CRUD Views Tests (Including Dual GET/POST Coverage)
# ==============================================================================

class ReaderCRUDTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_reader",
            password="password123",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.reader = Reader.objects.create(
            full_name="Alan Turing",
            email="alan@example.com",
            phone="+44 1234 5678",
            address="Bletchley Park",
        )

    def test_reader_list_view(self):
        response = self.client.get(reverse('library:reader-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/reader_list.html')
        self.assertContains(response, "Alan Turing")

    def test_reader_detail_view(self):
        response = self.client.get(reverse('library:reader-detail', args=[self.reader.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/reader_detail.html')
        self.assertContains(response, "Alan Turing")
        self.assertContains(response, "alan@example.com")

    def test_reader_create_view_get(self):
        response = self.client.get(reverse('library:reader-create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/reader_form.html')

    def test_reader_create_view_valid(self):
        response = self.client.post(reverse('library:reader-create'), {
            'full_name': 'Claude Shannon',
            'email': 'Shannon@BELL-LABS.com',  # Should be lowercased
            'phone': '+1-555-0199',
            'address': 'Bell Labs',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:reader-list'))
        reader = Reader.objects.get(full_name='Claude Shannon')
        self.assertEqual(reader.email, 'shannon@bell-labs.com')

    def test_reader_create_view_empty_email_normalized_to_none(self):
        response = self.client.post(reverse('library:reader-create'), {
            'full_name': 'No Email Reader',
            'email': '',
            'phone': '+1-555-0123',
            'address': 'Unknown',
        })
        self.assertEqual(response.status_code, 302)
        reader = Reader.objects.get(full_name='No Email Reader')
        self.assertIsNone(reader.email)

    def test_reader_multiple_empty_emails_succeed(self):
        self.client.post(reverse('library:reader-create'), {
            'full_name': 'Reader One',
            'email': '',
            'phone': '+1-555-1111',
        })
        self.client.post(reverse('library:reader-create'), {
            'full_name': 'Reader Two',
            'email': '   ',
            'phone': '+1-555-2222',
        })
        r1 = Reader.objects.get(full_name='Reader One')
        r2 = Reader.objects.get(full_name='Reader Two')
        self.assertIsNone(r1.email)
        self.assertIsNone(r2.email)
        self.assertNotEqual(r1.pk, r2.pk)

    def test_reader_update_view_get(self):
        response = self.client.get(reverse('library:reader-update', args=[self.reader.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/reader_form.html')

    def test_reader_update_view_post(self):
        response = self.client.post(reverse('library:reader-update', args=[self.reader.pk]), {
            'full_name': 'Alan M. Turing',
            'email': 'alan.turing@manchester.ac.uk',
            'phone': '+44 161 275 0000',
            'address': 'Manchester',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:reader-list'))
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.full_name, 'Alan M. Turing')
        self.assertEqual(self.reader.email, 'alan.turing@manchester.ac.uk')

    def test_reader_delete_view_get_confirm_page(self):
        response = self.client.get(reverse('library:reader-delete', args=[self.reader.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/reader_confirm_delete.html')

    def test_reader_delete_view_post(self):
        response = self.client.post(reverse('library:reader-delete', args=[self.reader.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:reader-list'))
        self.assertFalse(Reader.objects.filter(pk=self.reader.pk).exists())


class BookSearchFilterPaginationTests(TestCase):
    """
    Test suite for Phase 07: Search, Filtering, Sorting, and Pagination
    on the Book catalog listing page.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username="search_user",
            password="password123",
        )
        self.client.force_login(self.user)
        self.cat_tech = Category.objects.create(name='Technology', description='Tech books')
        self.cat_fiction = Category.objects.create(name='Science Fiction', description='Sci-Fi')
        self.cat_history = Category.objects.create(name='History', description='Historical texts')

        # Create distinct test books
        self.book1 = Book.objects.create(
            title='Alpha Algorithms in Python',
            author='Alice Smith',
            isbn='9781111111111',
            category=self.cat_tech,
            total_copies=5,
            available_copies=5,
        )
        self.book2 = Book.objects.create(
            title='Beta Cloud Architectures',
            author='Bob Jones',
            isbn='9782222222222',
            category=self.cat_tech,
            total_copies=3,
            available_copies=0,  # Unavailable
        )
        self.book3 = Book.objects.create(
            title='Cyberpunk Odyssey',
            author='Charlie Brown',
            isbn='9783333333333',
            category=self.cat_fiction,
            total_copies=4,
            available_copies=2,
        )
        self.book4 = Book.objects.create(
            title='Dune Chronicles',
            author='Frank Herbert',
            isbn='9784444444444',
            category=self.cat_fiction,
            total_copies=2,
            available_copies=0,  # Unavailable
        )

    # 1. Search Tests
    def test_search_by_title_case_insensitive(self):
        response = self.client.get(reverse('library:book-list'), {'q': 'algorithms'})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0], self.book1)

    def test_search_by_author(self):
        response = self.client.get(reverse('library:book-list'), {'q': 'Herbert'})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0], self.book4)

    def test_search_by_isbn(self):
        response = self.client.get(reverse('library:book-list'), {'q': '9783333333333'})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0], self.book3)

    def test_search_by_category_name(self):
        response = self.client.get(reverse('library:book-list'), {'q': 'Science Fiction'})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 2)
        titles = {b.title for b in books}
        self.assertEqual(titles, {'Cyberpunk Odyssey', 'Dune Chronicles'})

    def test_search_trims_whitespace(self):
        response = self.client.get(reverse('library:book-list'), {'q': '   Cloud   '})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0], self.book2)

    def test_search_empty_string_returns_all(self):
        response = self.client.get(reverse('library:book-list'), {'q': '   '})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 4)

    def test_search_excessively_long_capped_safely(self):
        long_query = 'a' * 200
        response = self.client.get(reverse('library:book-list'), {'q': long_query})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['search_query']), 100)

    def test_search_no_results_renders_empty_state(self):
        response = self.client.get(reverse('library:book-list'), {'q': 'NonExistentBook12345'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['books']), 0)
        self.assertTrue(response.context['is_filtered'])
        self.assertContains(response, "No Matching Books Found")
        self.assertContains(response, "Clear Filters")

    # 2. Category Filtering Tests
    def test_filter_by_category_valid_id(self):
        response = self.client.get(reverse('library:book-list'), {'category': self.cat_tech.pk})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 2)
        for b in books:
            self.assertEqual(b.category, self.cat_tech)

    def test_filter_by_category_empty_category(self):
        response = self.client.get(reverse('library:book-list'), {'category': self.cat_history.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['books']), 0)

    def test_filter_by_category_invalid_non_numeric_id_ignored(self):
        response = self.client.get(reverse('library:book-list'), {'category': 'not-an-id'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['books']), 4)

    # 3. Availability Filtering Tests
    def test_filter_availability_available_only(self):
        response = self.client.get(reverse('library:book-list'), {'availability': 'available'})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 2)
        for b in books:
            self.assertGreater(b.available_copies, 0)
        titles = {b.title for b in books}
        self.assertEqual(titles, {'Alpha Algorithms in Python', 'Cyberpunk Odyssey'})

    def test_filter_availability_unavailable_only(self):
        response = self.client.get(reverse('library:book-list'), {'availability': 'unavailable'})
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 2)
        for b in books:
            self.assertEqual(b.available_copies, 0)
        titles = {b.title for b in books}
        self.assertEqual(titles, {'Beta Cloud Architectures', 'Dune Chronicles'})

    def test_filter_availability_all_or_blank(self):
        response = self.client.get(reverse('library:book-list'), {'availability': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['books']), 4)

    # 4. Sorting Tests
    def test_sorting_title_asc(self):
        response = self.client.get(reverse('library:book-list'), {'sort': 'title_asc'})
        self.assertEqual(response.status_code, 200)
        titles = [b.title for b in response.context['books']]
        self.assertEqual(titles, sorted(titles))

    def test_sorting_title_desc(self):
        response = self.client.get(reverse('library:book-list'), {'sort': 'title_desc'})
        self.assertEqual(response.status_code, 200)
        titles = [b.title for b in response.context['books']]
        self.assertEqual(titles, sorted(titles, reverse=True))

    def test_sorting_author_asc(self):
        response = self.client.get(reverse('library:book-list'), {'sort': 'author_asc'})
        self.assertEqual(response.status_code, 200)
        authors = [b.author for b in response.context['books']]
        self.assertEqual(authors, sorted(authors))

    def test_sorting_oldest_first(self):
        response = self.client.get(reverse('library:book-list'), {'sort': 'oldest'})
        self.assertEqual(response.status_code, 200)
        books = list(response.context['books'])
        self.assertEqual(books[0], self.book1)

    def test_sorting_newest_first(self):
        response = self.client.get(reverse('library:book-list'), {'sort': 'newest'})
        self.assertEqual(response.status_code, 200)
        books = list(response.context['books'])
        self.assertEqual(books[0], self.book4)

    def test_sorting_invalid_parameter_falls_back_safely(self):
        response = self.client.get(reverse('library:book-list'), {'sort': 'malicious_column_name'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_sort'], 'newest')

    # 5. Combined Filtering Tests
    def test_combined_search_category_and_availability(self):
        response = self.client.get(reverse('library:book-list'), {
            'q': 'Cloud',
            'category': self.cat_tech.pk,
            'availability': 'unavailable',
            'sort': 'title_asc',
        })
        self.assertEqual(response.status_code, 200)
        books = response.context['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0], self.book2)

    def test_is_filtered_flag_detection(self):
        # Clean request
        res1 = self.client.get(reverse('library:book-list'))
        self.assertFalse(res1.context['is_filtered'])

        # With search query
        res2 = self.client.get(reverse('library:book-list'), {'q': 'Alpha'})
        self.assertTrue(res2.context['is_filtered'])

        # With category
        res3 = self.client.get(reverse('library:book-list'), {'category': self.cat_tech.pk})
        self.assertTrue(res3.context['is_filtered'])

        # With availability
        res4 = self.client.get(reverse('library:book-list'), {'availability': 'available'})
        self.assertTrue(res4.context['is_filtered'])

        # With non-default sort
        res5 = self.client.get(reverse('library:book-list'), {'sort': 'title_asc'})
        self.assertTrue(res5.context['is_filtered'])

    # 6. Pagination Tests
    def test_pagination_ten_items_per_page(self):
        # Create additional 11 books to total 15 books
        for i in range(1, 12):
            Book.objects.create(
                title=f'Pagination Book {i:02d}',
                author=f'Author {i}',
                category=self.cat_tech,
                total_copies=1,
                available_copies=1,
            )

        # Page 1
        res_p1 = self.client.get(reverse('library:book-list'))
        self.assertEqual(res_p1.status_code, 200)
        self.assertTrue(res_p1.context['is_paginated'])
        self.assertEqual(len(res_p1.context['books']), 10)
        self.assertEqual(res_p1.context['paginator'].count, 15)
        self.assertEqual(res_p1.context['paginator'].num_pages, 2)
        self.assertEqual(res_p1.context['page_obj'].number, 1)

        # Page 2
        res_p2 = self.client.get(reverse('library:book-list'), {'page': 2})
        self.assertEqual(res_p2.status_code, 200)
        self.assertEqual(len(res_p2.context['books']), 5)
        self.assertEqual(res_p2.context['page_obj'].number, 2)

    def test_pagination_invalid_page_returns_first_page(self):
        response = self.client.get(reverse('library:book-list'), {'page': 'invalid_page_num'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)

    def test_pagination_out_of_range_page_returns_last_page(self):
        # Create additional books so there are 2 pages
        for i in range(1, 12):
            Book.objects.create(
                title=f'Extra Book {i}',
                author='Author',
                category=self.cat_tech,
                total_copies=1,
                available_copies=1,
            )
        response = self.client.get(reverse('library:book-list'), {'page': 9999})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 2)

    def test_pagination_negative_page_returns_first_page(self):
        response = self.client.get(reverse('library:book-list'), {'page': -5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)

    def test_pagination_preserves_filter_querystring(self):
        # Create additional books so there are 2 pages of Tech books
        for i in range(1, 12):
            Book.objects.create(
                title=f'Extra Tech Book {i}',
                author='Tech Author',
                category=self.cat_tech,
                total_copies=2,
                available_copies=1,
            )
        response = self.client.get(reverse('library:book-list'), {
            'q': 'Tech',
            'category': self.cat_tech.pk,
            'availability': 'available',
            'sort': 'title_asc',
            'page': 1,
        })
        self.assertEqual(response.status_code, 200)
        querystring = response.context['querystring']
        # 'page' should NOT be in querystring
        self.assertNotIn('page=', querystring)
        # All filters should be in querystring
        self.assertIn('q=Tech', querystring)
        self.assertIn(f'category={self.cat_tech.pk}', querystring)
        self.assertIn('availability=available', querystring)
        self.assertIn('sort=title_asc', querystring)
        # Verify pagination link in HTML carries the preserved querystring
        self.assertContains(response, f'q=Tech')
        self.assertContains(response, f'sort=title_asc&page=2')


# ==============================================================================
# Phase 08 Tests: Book Circulation, Issuing, and Returning
# ==============================================================================

class BorrowRecordModelTests(TestCase):
    """
    Unit tests for the BorrowRecord model, integrity constraints, and overdue calculation.
    """
    def setUp(self):
        self.category = Category.objects.create(name="Circulation Category")
        self.book = Book.objects.create(
            title="Clean Architecture",
            author="Robert C. Martin",
            isbn="9780134494164",
            category=self.category,
            total_copies=5,
            available_copies=5,
        )
        self.reader = Reader.objects.create(
            full_name="Grace Hopper",
            email="grace.hopper@navy.mil",
            phone="+1 555-0100",
        )

    def test_valid_borrow_record_creation(self):
        issue_date = timezone.localdate()
        due_date = issue_date + timedelta(days=14)
        record = BorrowRecord.objects.create(
            book=self.book,
            reader=self.reader,
            issue_date=issue_date,
            due_date=due_date,
            status=BorrowRecord.STATUS_ACTIVE,
        )
        self.assertEqual(record.status, BorrowRecord.STATUS_ACTIVE)
        self.assertEqual(record.issue_date, issue_date)
        self.assertEqual(record.due_date, due_date)
        self.assertIsNone(record.returned_at)
        self.assertFalse(record.is_overdue)
        self.assertIn("Clean Architecture", str(record))
        self.assertIn("Grace Hopper", str(record))

    def test_borrow_record_invalid_due_date_clean(self):
        today = timezone.localdate()
        record = BorrowRecord(
            book=self.book,
            reader=self.reader,
            issue_date=today,
            due_date=today - timedelta(days=1),
            status=BorrowRecord.STATUS_ACTIVE,
        )
        with self.assertRaises(ValidationError) as ctx:
            record.full_clean()
        self.assertIn("due_date", ctx.exception.message_dict)

    def test_borrow_record_check_constraint_db(self):
        today = timezone.localdate()
        with self.assertRaises(IntegrityError):
            BorrowRecord.objects.create(
                book=self.book,
                reader=self.reader,
                issue_date=today,
                due_date=today - timedelta(days=2),
                status=BorrowRecord.STATUS_ACTIVE,
            )

    def test_overdue_property_calculation(self):
        today = timezone.localdate()
        # 1. Active overdue loan (due yesterday)
        overdue_record = BorrowRecord.objects.create(
            book=self.book,
            reader=self.reader,
            issue_date=today - timedelta(days=15),
            due_date=today - timedelta(days=1),
            status=BorrowRecord.STATUS_ACTIVE,
        )
        self.assertTrue(overdue_record.is_overdue)

        # 2. Returned loan (due date was in past, but returned)
        overdue_record.status = BorrowRecord.STATUS_RETURNED
        overdue_record.returned_at = timezone.now()
        overdue_record.save()
        self.assertFalse(overdue_record.is_overdue)

        # 3. Active future loan (due tomorrow)
        future_record = BorrowRecord.objects.create(
            book=self.book,
            reader=self.reader,
            issue_date=today,
            due_date=today + timedelta(days=7),
            status=BorrowRecord.STATUS_ACTIVE,
        )
        self.assertFalse(future_record.is_overdue)

    def test_duplicate_active_borrow_record_prevented(self):
        today = timezone.localdate()
        BorrowRecord.objects.create(
            book=self.book,
            reader=self.reader,
            issue_date=today,
            due_date=today + timedelta(days=14),
            status=BorrowRecord.STATUS_ACTIVE,
        )
        # Attempt to create a second active loan for same reader & book
        duplicate = BorrowRecord(
            book=self.book,
            reader=self.reader,
            issue_date=today,
            due_date=today + timedelta(days=14),
            status=BorrowRecord.STATUS_ACTIVE,
        )
        with self.assertRaises(ValidationError) as ctx:
            duplicate.full_clean()
        self.assertIn("active borrowing record", str(ctx.exception))


class BorrowingServiceTests(TestCase):
    """
    Tests for circulation business logic, inventory tracking, and concurrency safeguards
    implemented in apps/library/services/borrowing.py.
    """
    def setUp(self):
        self.category = Category.objects.create(name="Circulation Services")
        self.book = Book.objects.create(
            title="Design Patterns",
            author="Gang of Four",
            isbn="9780201633610",
            category=self.category,
            total_copies=2,
            available_copies=2,
        )
        self.reader1 = Reader.objects.create(full_name="Reader One", email="r1@example.com")
        self.reader2 = Reader.objects.create(full_name="Reader Two", email="r2@example.com")

    def test_issue_book_success(self):
        record = issue_book(book=self.book, reader=self.reader1)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(record.status, BorrowRecord.STATUS_ACTIVE)
        self.assertEqual(record.reader, self.reader1)
        self.assertEqual(record.book, self.book)
        self.assertEqual(record.due_date, timezone.localdate() + timedelta(days=14))

    def test_issue_book_unavailable_zero_copies_rejected(self):
        # Deplete copies to 0
        self.book.available_copies = 0
        self.book.save()

        with self.assertRaises(BorrowingError) as ctx:
            issue_book(book=self.book, reader=self.reader1)
        self.assertIn("No copies", str(ctx.exception))
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 0)

    def test_issue_book_duplicate_active_loan_rejected(self):
        issue_book(book=self.book, reader=self.reader1)
        with self.assertRaises(BorrowingError) as ctx:
            issue_book(book=self.book, reader=self.reader1)
        self.assertIn("already has an active loan", str(ctx.exception))
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_issue_book_multiple_readers_different_copies(self):
        r1_record = issue_book(book=self.book, reader=self.reader1)
        r2_record = issue_book(book=self.book, reader=self.reader2)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 0)
        self.assertNotEqual(r1_record.pk, r2_record.pk)

    def test_issue_book_invalid_reader_or_book(self):
        with self.assertRaises(BorrowingError):
            issue_book(book=99999, reader=self.reader1)
        with self.assertRaises(BorrowingError):
            issue_book(book=self.book, reader=99999)

    def test_issue_book_past_due_date_rejected(self):
        today = timezone.localdate()
        with self.assertRaises(BorrowingError) as ctx:
            issue_book(book=self.book, reader=self.reader1, due_date=today - timedelta(days=1))
        self.assertIn("Due date cannot be earlier", str(ctx.exception))

    def test_return_book_success(self):
        record = issue_book(book=self.book, reader=self.reader1)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

        returned_record = return_book(borrow_record_id=record.pk)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)
        self.assertEqual(returned_record.status, BorrowRecord.STATUS_RETURNED)
        self.assertIsNotNone(returned_record.returned_at)

    def test_return_book_already_returned_raises_error(self):
        record = issue_book(book=self.book, reader=self.reader1)
        return_book(borrow_record_id=record.pk)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

        # Attempt to return again
        with self.assertRaises(BorrowingError) as ctx:
            return_book(borrow_record_id=record.pk)
        self.assertIn("already been marked as returned", str(ctx.exception))
        self.book.refresh_from_db()
        # Verify inventory was NOT incremented again past total_copies
        self.assertEqual(self.book.available_copies, 2)

    def test_return_book_cannot_exceed_total_copies(self):
        record = issue_book(book=self.book, reader=self.reader1)
        # Artificially set available_copies to total_copies
        self.book.available_copies = self.book.total_copies
        self.book.save()

        with self.assertRaises(BorrowingError) as ctx:
            return_book(borrow_record_id=record.pk)
        self.assertIn("already at maximum capacity", str(ctx.exception))

    def test_return_book_invalid_id(self):
        with self.assertRaises(BorrowingError):
            return_book(borrow_record_id=99999)


class BorrowingViewTests(TestCase):
    """
    Tests for circulation views, URL endpoints, forms, and template flows.
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_borrow",
            password="password123",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.category = Category.objects.create(name="View Test Genre")
        self.book = Book.objects.create(
            title="Refactoring",
            author="Martin Fowler",
            isbn="9780201485677",
            category=self.category,
            total_copies=3,
            available_copies=3,
        )
        self.reader = Reader.objects.create(
            full_name="Ada Lovelace",
            email="ada@firstprogrammer.org",
            phone="+44 20 7946 0991",
        )

    def test_borrow_list_view_get(self):
        response = self.client.get(reverse('library:borrow-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/borrow_list.html')
        self.assertEqual(response.context['current_status'], 'all')

    def test_borrow_list_filtering_by_status(self):
        today = timezone.localdate()
        # Active loan
        rec_active = BorrowRecord.objects.create(
            book=self.book,
            reader=self.reader,
            issue_date=today,
            due_date=today + timedelta(days=10),
            status=BorrowRecord.STATUS_ACTIVE,
        )
        # Returned loan
        reader2 = Reader.objects.create(full_name="Reader 2")
        rec_returned = BorrowRecord.objects.create(
            book=self.book,
            reader=reader2,
            issue_date=today - timedelta(days=20),
            due_date=today - timedelta(days=6),
            returned_at=timezone.now(),
            status=BorrowRecord.STATUS_RETURNED,
        )
        # Overdue loan
        reader3 = Reader.objects.create(full_name="Reader 3")
        rec_overdue = BorrowRecord.objects.create(
            book=self.book,
            reader=reader3,
            issue_date=today - timedelta(days=25),
            due_date=today - timedelta(days=5),
            status=BorrowRecord.STATUS_ACTIVE,
        )

        # Test active filter
        res_active = self.client.get(reverse('library:borrow-active'))
        self.assertEqual(res_active.status_code, 200)
        active_records = list(res_active.context['borrow_records'])
        self.assertIn(rec_active, active_records)
        self.assertIn(rec_overdue, active_records)  # overdue is still active
        self.assertNotIn(rec_returned, active_records)

        # Test returned filter
        res_returned = self.client.get(reverse('library:borrow-returned'))
        self.assertEqual(res_returned.status_code, 200)
        returned_records = list(res_returned.context['borrow_records'])
        self.assertIn(rec_returned, returned_records)
        self.assertNotIn(rec_active, returned_records)

        # Test overdue filter
        res_overdue = self.client.get(reverse('library:borrow-overdue'))
        self.assertEqual(res_overdue.status_code, 200)
        overdue_records = list(res_overdue.context['borrow_records'])
        self.assertIn(rec_overdue, overdue_records)
        self.assertNotIn(rec_active, overdue_records)
        self.assertNotIn(rec_returned, overdue_records)

    def test_borrow_list_search(self):
        record = issue_book(book=self.book, reader=self.reader)
        response = self.client.get(reverse('library:borrow-list'), {'q': 'Ada'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['borrow_records']), 1)
        self.assertEqual(response.context['borrow_records'][0], record)

    def test_borrow_detail_view_get(self):
        record = issue_book(book=self.book, reader=self.reader)
        response = self.client.get(reverse('library:borrow-detail', args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/borrow_detail.html')
        self.assertEqual(response.context['record'], record)

    def test_borrow_issue_view_get(self):
        response = self.client.get(reverse('library:borrow-issue'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/borrow_form.html')
        self.assertIsInstance(response.context['form'], BorrowIssueForm)

    def test_borrow_issue_view_post_valid(self):
        due_date = timezone.localdate() + timedelta(days=14)
        response = self.client.post(reverse('library:borrow-issue'), {
            'reader': self.reader.pk,
            'book': self.book.pk,
            'due_date': due_date.strftime('%Y-%m-%d'),
        })
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)
        record = BorrowRecord.objects.get(reader=self.reader, book=self.book)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:borrow-detail', args=[record.pk]))

    def test_borrow_issue_view_post_unavailable_fails(self):
        self.book.available_copies = 0
        self.book.save()
        due_date = timezone.localdate() + timedelta(days=14)
        response = self.client.post(reverse('library:borrow-issue'), {
            'reader': self.reader.pk,
            'book': self.book.pk,
            'due_date': due_date.strftime('%Y-%m-%d'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('book', response.context['form'].errors)

    def test_borrow_issue_view_post_duplicate_active_fails(self):
        issue_book(book=self.book, reader=self.reader)
        due_date = timezone.localdate() + timedelta(days=14)
        response = self.client.post(reverse('library:borrow-issue'), {
            'reader': self.reader.pk,
            'book': self.book.pk,
            'due_date': due_date.strftime('%Y-%m-%d'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'book',
            f"Reader '{self.reader.full_name}' already has an active loan for '{self.book.title}'."
        )

    def test_borrow_return_view_get(self):
        record = issue_book(book=self.book, reader=self.reader)
        response = self.client.get(reverse('library:borrow-return', args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'library/borrow_confirm_return.html')

    def test_borrow_return_view_post_successful(self):
        record = issue_book(book=self.book, reader=self.reader)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

        response = self.client.post(reverse('library:borrow-return', args=[record.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:borrow-detail', args=[record.pk]))
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 3)
        record.refresh_from_db()
        self.assertEqual(record.status, BorrowRecord.STATUS_RETURNED)

    def test_borrow_return_view_already_returned_redirects(self):
        record = issue_book(book=self.book, reader=self.reader)
        return_book(record.pk)

        # GET on already returned record redirects to detail
        response_get = self.client.get(reverse('library:borrow-return', args=[record.pk]))
        self.assertEqual(response_get.status_code, 302)
        self.assertRedirects(response_get, reverse('library:borrow-detail', args=[record.pk]))

        # POST on already returned record redirects to detail without error
        response_post = self.client.post(reverse('library:borrow-return', args=[record.pk]))
        self.assertEqual(response_post.status_code, 302)
        self.assertRedirects(response_post, reverse('library:borrow-detail', args=[record.pk]))

