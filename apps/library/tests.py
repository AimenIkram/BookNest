import datetime
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.library.models import Book, Category, Reader


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
# Category CRUD Views Tests
# ==============================================================================

class CategoryCRUDTests(TestCase):
    def setUp(self):
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
        # Create a book under this category to verify association rendering
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

    def test_category_update_view(self):
        response = self.client.post(reverse('library:category-update', args=[self.category.pk]), {
            'name': 'Modern Philosophy',
            'description': 'Updated description.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:category-list'))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Modern Philosophy')

    def test_category_delete_without_books_succeeds(self):
        empty_category = Category.objects.create(name='Disposable')
        response = self.client.post(reverse('library:category-delete', args=[empty_category.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:category-list'))
        self.assertFalse(Category.objects.filter(pk=empty_category.pk).exists())

    def test_category_delete_with_books_handles_protected_error(self):
        # Category contains a book, so deletion must be blocked gracefully
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
        # Should redirect back to detail view with error message, NOT crash with 500
        self.assertRedirects(response, reverse('library:category-detail', args=[self.category.pk]))
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        
        # Verify error message delivered
        messages = list(response.context['messages'])
        self.assertTrue(any("Cannot delete category" in str(m) for m in messages))


# ==============================================================================
# Book CRUD Views Tests
# ==============================================================================

class BookCRUDTests(TestCase):
    def setUp(self):
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

    def test_book_create_view_valid(self):
        response = self.client.post(reverse('library:book-create'), {
            'title': '1984',
            'author': 'George Orwell',
            'isbn': '9780451524935',
            'category': self.category.pk,
            'total_copies': 6,
            'available_copies': 6,
            'publication_date': '1949-06-08',
            'description': 'Dystopian classic.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:book-list'))
        self.assertTrue(Book.objects.filter(title='1984').exists())

    def test_book_create_view_invalid_copies(self):
        response = self.client.post(reverse('library:book-create'), {
            'title': 'Invalid Book',
            'author': 'Test Author',
            'category': self.category.pk,
            'total_copies': 2,
            'available_copies': 5,  # Exceeds total
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'available_copies',
            "Available copies cannot exceed total copies."
        )

    def test_book_update_view(self):
        response = self.client.post(reverse('library:book-update', args=[self.book.pk]), {
            'title': 'The Hobbit: Illustrated Edition',
            'author': 'J.R.R. Tolkien',
            'isbn': '9780547928227',
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

    def test_book_delete_view(self):
        response = self.client.post(reverse('library:book-delete', args=[self.book.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:book-list'))
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())


# ==============================================================================
# Reader CRUD Views Tests
# ==============================================================================

class ReaderCRUDTests(TestCase):
    def setUp(self):
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

    def test_reader_create_view_valid(self):
        response = self.client.post(reverse('library:reader-create'), {
            'full_name': 'Claude Shannon',
            'email': 'shannon@example.com',
            'phone': '123-456',
            'address': 'Bell Labs',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:reader-list'))
        self.assertTrue(Reader.objects.filter(full_name='Claude Shannon').exists())

    def test_reader_create_view_empty_email_normalized_to_none(self):
        response = self.client.post(reverse('library:reader-create'), {
            'full_name': 'No Email Reader',
            'email': '',  # Empty email in form
            'phone': '555-0000',
            'address': 'Unknown',
        })
        self.assertEqual(response.status_code, 302)
        reader = Reader.objects.get(full_name='No Email Reader')
        self.assertIsNone(reader.email)

    def test_reader_multiple_empty_emails_succeed(self):
        # Multiple readers with empty emails must not violate the unique constraint
        self.client.post(reverse('library:reader-create'), {
            'full_name': 'Reader One',
            'email': '',
        })
        self.client.post(reverse('library:reader-create'), {
            'full_name': 'Reader Two',
            'email': '   ',  # Whitespace only
        })
        r1 = Reader.objects.get(full_name='Reader One')
        r2 = Reader.objects.get(full_name='Reader Two')
        self.assertIsNone(r1.email)
        self.assertIsNone(r2.email)
        self.assertNotEqual(r1.pk, r2.pk)

    def test_reader_update_view(self):
        response = self.client.post(reverse('library:reader-update', args=[self.reader.pk]), {
            'full_name': 'Alan M. Turing',
            'email': 'alan.turing@manchester.ac.uk',
            'phone': '+44 9999 0000',
            'address': 'Manchester',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:reader-list'))
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.full_name, 'Alan M. Turing')
        self.assertEqual(self.reader.email, 'alan.turing@manchester.ac.uk')

    def test_reader_delete_view(self):
        response = self.client.post(reverse('library:reader-delete', args=[self.reader.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('library:reader-list'))
        self.assertFalse(Reader.objects.filter(pk=self.reader.pk).exists())
