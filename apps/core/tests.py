from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from apps.core.views import home_view
from apps.library.models import Book, BorrowRecord, Category, Reader


class HomePageTests(TestCase):
    """
    Tests for the BookNest core home view, template inheritance,
    and foundational architectural assertions.
    """
    def setUp(self):
        self.user = User.objects.create_user(
            username='home_patron',
            password='password123',
        )
        self.client.force_login(self.user)
        self.url = reverse('core:home')
        self.response = self.client.get(self.url)

    def test_home_page_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_home_page_template_used(self):
        self.assertTemplateUsed(self.response, 'core/home.html')
        self.assertTemplateUsed(self.response, 'base.html')

    def test_home_page_contains_expected_content(self):
        self.assertContains(self.response, 'BookNest')
        self.assertContains(self.response, 'Library Overview')

    def test_home_url_resolves_correctly(self):
        resolved = resolve('/')
        self.assertEqual(resolved.func, home_view)
        self.assertEqual(resolved.namespace, 'core')


class DashboardMetricsTests(TestCase):
    """
    Comprehensive tests for the Phase 09/10 Administrative Dashboard:
    live statistics, recent circulation activity, overdue detection,
    and inventory stock alerts.
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_dashboard',
            password='password123',
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.url = reverse('core:home')

    def test_dashboard_statistics_empty_state(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['total_books'], 0)
        self.assertEqual(ctx['total_categories'], 0)
        self.assertEqual(ctx['total_readers'], 0)
        self.assertEqual(ctx['total_copies'], 0)
        self.assertEqual(ctx['available_copies'], 0)
        self.assertEqual(ctx['borrowed_copies'], 0)
        self.assertEqual(ctx['inventory_utilization'], 0)
        self.assertEqual(ctx['active_borrows'], 0)
        self.assertEqual(ctx['returned_borrows'], 0)
        self.assertEqual(ctx['overdue_borrows'], 0)
        self.assertEqual(len(ctx['recent_activity']), 0)
        self.assertEqual(len(ctx['overdue_records']), 0)
        self.assertEqual(len(ctx['low_inventory_books']), 0)

    def test_dashboard_statistics_with_real_data(self):
        today = timezone.localdate()
        cat1 = Category.objects.create(name="Fiction")
        cat2 = Category.objects.create(name="Science")

        # Book 1: 5 total, 3 available (2 borrowed)
        b1 = Book.objects.create(
            title="Dune", author="Frank Herbert", category=cat1,
            total_copies=5, available_copies=3
        )
        # Book 2: 3 total, 3 available (0 borrowed)
        b2 = Book.objects.create(
            title="Cosmos", author="Carl Sagan", category=cat2,
            total_copies=3, available_copies=3
        )
        # Book 3: 1 total, 0 available (1 borrowed, out of stock)
        b3 = Book.objects.create(
            title="Neuromancer", author="William Gibson", category=cat1,
            total_copies=1, available_copies=0
        )

        r1 = Reader.objects.create(full_name="Alice Smith", email="alice@test.com")
        r2 = Reader.objects.create(full_name="Bob Jones", email="bob@test.com")
        r3 = Reader.objects.create(full_name="Charlie Brown", email="charlie@test.com")

        # Active normal loan (due in future)
        rec_active = BorrowRecord.objects.create(
            book=b1, reader=r1, issue_date=today,
            due_date=today + timedelta(days=14), status=BorrowRecord.STATUS_ACTIVE
        )
        # Active overdue loan (due in past)
        rec_overdue = BorrowRecord.objects.create(
            book=b3, reader=r2, issue_date=today - timedelta(days=20),
            due_date=today - timedelta(days=6), status=BorrowRecord.STATUS_ACTIVE
        )
        # Returned loan
        rec_returned = BorrowRecord.objects.create(
            book=b1, reader=r3, issue_date=today - timedelta(days=30),
            due_date=today - timedelta(days=16), returned_at=timezone.now(),
            status=BorrowRecord.STATUS_RETURNED
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        # Verify core counts
        self.assertEqual(ctx['total_books'], 3)
        self.assertEqual(ctx['total_categories'], 2)
        self.assertEqual(ctx['total_readers'], 3)

        # Verify inventory aggregations (5 + 3 + 1 = 9 total, 3 + 3 + 0 = 6 available, 3 borrowed)
        self.assertEqual(ctx['total_copies'], 9)
        self.assertEqual(ctx['available_copies'], 6)
        self.assertEqual(ctx['borrowed_copies'], 3)
        self.assertEqual(ctx['inventory_utilization'], round((3 / 9) * 100, 1))

        # Verify circulation loan counts
        self.assertEqual(ctx['active_borrows'], 2)
        self.assertEqual(ctx['overdue_borrows'], 1)
        self.assertEqual(ctx['returned_borrows'], 1)

        # Verify recent activity includes latest events
        self.assertEqual(len(ctx['recent_activity']), 3)

        # Verify overdue records contains ONLY active overdue loans
        self.assertEqual(len(ctx['overdue_records']), 1)
        self.assertEqual(ctx['overdue_records'][0], rec_overdue)

        # Verify low inventory books (b3 with 0 copies, and any <= 1)
        low_stock_ids = [b.pk for b in ctx['low_inventory_books']]
        self.assertIn(b3.pk, low_stock_ids)

    def test_dashboard_quick_actions_links_rendered_for_staff(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('library:borrow-issue'))
        self.assertContains(response, reverse('library:book-create'))
        self.assertContains(response, reverse('library:reader-create'))
        self.assertContains(response, reverse('library:category-create'))
        self.assertContains(response, reverse('library:book-list'))


class AuthenticationTests(TestCase):
    """
    Comprehensive test suite for Phase 10 Authentication:
    Login, incorrect password, logout, session state, redirect preservation.
    """
    def setUp(self):
        self.username = "testuser"
        self.password = "Secr3t_P@ssw0rd!"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email="testuser@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        self.login_url = reverse('core:login')
        self.logout_url = reverse('core:logout')
        self.home_url = reverse('core:home')

    def test_login_page_renders_successfully(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/login.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, 'Sign In')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_login_successful_redirects_to_dashboard(self):
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password,
        })
        self.assertRedirects(response, self.home_url)
        # Check that user is authenticated in the session
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_redirect_preserves_next_parameter(self):
        destination = reverse('library:book-list')
        url_with_next = f"{self.login_url}?next={destination}"
        get_response = self.client.get(url_with_next)
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, f'value="{destination}"')

        post_response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password,
            'next': destination,
        })
        self.assertRedirects(post_response, destination)

    def test_login_incorrect_password_fails(self):
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': 'WrongPasswordXYZ',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/login.html')
        self.assertFalse(response.context['user'].is_authenticated)
        self.assertContains(response, "Please enter a correct username and password")

    def test_login_nonexistent_user_fails(self):
        response = self.client.post(self.login_url, {
            'username': 'nonexistent_user',
            'password': 'somepassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/login.html')
        self.assertFalse(response.context['user'].is_authenticated)

    def test_already_authenticated_user_redirected_away_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.home_url)

    def test_logout_via_csrf_protected_post(self):
        self.client.force_login(self.user)
        # Ensure session shows user is authenticated
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.login_url)
        # Verify user is logged out of the session
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_get_method_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 405)

    def test_login_csrf_protection_enforced(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.get(self.login_url)
        # Attempt POST without CSRF token
        response = csrf_client.post(self.login_url, {
            'username': self.username,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 403)

    def test_logout_csrf_protection_enforced(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        # Attempt POST without CSRF token
        response = csrf_client.post(self.logout_url)
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_redirected_to_login_from_home(self):
        response = self.client.get(self.home_url)
        expected_redirect = f"{self.login_url}?next={self.home_url}"
        self.assertRedirects(response, expected_redirect)

    def test_unauthenticated_user_redirected_from_protected_library_urls(self):
        protected_urls = [
            reverse('library:book-list'),
            reverse('library:book-create'),
            reverse('library:category-list'),
            reverse('library:category-create'),
            reverse('library:reader-list'),
            reverse('library:reader-create'),
            reverse('library:borrow-list'),
            reverse('library:borrow-issue'),
        ]
        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                expected_redirect = f"{self.login_url}?next={url}"
                self.assertRedirects(response, expected_redirect)


class PermissionAccessControlTests(TestCase):
    """
    Comprehensive test suite for Phase 10 Permissions and Roles:
    - Regular users: Can view dashboard, books, categories, readers, borrow records.
                    Cannot create, update, delete, issue, or return.
    - Staff users: Full administrative access.
    """
    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular_patron",
            password="password123",
            is_staff=False,
            is_superuser=False,
        )
        self.staff_user = User.objects.create_user(
            username="staff_member",
            password="password123",
            is_staff=True,
            is_superuser=False,
        )
        self.superuser = User.objects.create_superuser(
            username="super_admin",
            password="password123",
            email="admin@example.com",
        )

        self.category = Category.objects.create(
            name="Science Fiction",
            description="Futuristic literature."
        )
        self.book = Book.objects.create(
            title="Foundation",
            author="Isaac Asimov",
            isbn="9780553293357",
            category=self.category,
            total_copies=5,
            available_copies=5,
        )
        self.reader = Reader.objects.create(
            full_name="Arthur Dent",
            email="arthur@galaxy.org",
        )
        self.borrow_record = BorrowRecord.objects.create(
            book=self.book,
            reader=self.reader,
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=14),
            status=BorrowRecord.STATUS_ACTIVE,
        )

    # --- Regular User Allowed Operations ---

    def test_regular_user_can_view_dashboard(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

    def test_regular_user_can_view_books_list_and_detail(self):
        self.client.force_login(self.regular_user)
        res_list = self.client.get(reverse('library:book-list'))
        self.assertEqual(res_list.status_code, 200)
        res_detail = self.client.get(reverse('library:book-detail', args=[self.book.pk]))
        self.assertEqual(res_detail.status_code, 200)

    def test_regular_user_can_view_categories_list_and_detail(self):
        self.client.force_login(self.regular_user)
        res_list = self.client.get(reverse('library:category-list'))
        self.assertEqual(res_list.status_code, 200)
        res_detail = self.client.get(reverse('library:category-detail', args=[self.category.pk]))
        self.assertEqual(res_detail.status_code, 200)

    def test_regular_user_can_view_readers_list_and_detail(self):
        self.client.force_login(self.regular_user)
        res_list = self.client.get(reverse('library:reader-list'))
        self.assertEqual(res_list.status_code, 200)
        res_detail = self.client.get(reverse('library:reader-detail', args=[self.reader.pk]))
        self.assertEqual(res_detail.status_code, 200)

    def test_regular_user_can_view_borrowing_list_and_detail(self):
        self.client.force_login(self.regular_user)
        res_list = self.client.get(reverse('library:borrow-list'))
        self.assertEqual(res_list.status_code, 200)
        res_detail = self.client.get(reverse('library:borrow-detail', args=[self.borrow_record.pk]))
        self.assertEqual(res_detail.status_code, 200)

    # --- Regular User Denied Administrative Operations (403 Forbidden) ---

    def test_regular_user_cannot_create_book(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:book-create')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {
            'title': 'Unauthorized Book',
            'author': 'Hacker',
            'isbn': '9780000000000',
            'category': self.category.pk,
            'total_copies': 1,
            'available_copies': 1,
        }).status_code, 403)

    def test_regular_user_cannot_update_book(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:book-update', args=[self.book.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'title': 'Modified'}).status_code, 403)

    def test_regular_user_cannot_delete_book(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:book-delete', args=[self.book.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_regular_user_cannot_create_category(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:category-create')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'name': 'New Category'}).status_code, 403)

    def test_regular_user_cannot_update_category(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:category-update', args=[self.category.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'name': 'Modified Category'}).status_code, 403)

    def test_regular_user_cannot_delete_category(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:category-delete', args=[self.category.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_regular_user_cannot_create_reader(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:reader-create')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'full_name': 'New Reader'}).status_code, 403)

    def test_regular_user_cannot_update_reader(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:reader-update', args=[self.reader.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'full_name': 'Modified Reader'}).status_code, 403)

    def test_regular_user_cannot_delete_reader(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:reader-delete', args=[self.reader.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_regular_user_cannot_issue_book(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:borrow-issue')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {
            'reader': self.reader.pk,
            'book': self.book.pk,
            'due_date': timezone.localdate() + timedelta(days=7),
        }).status_code, 403)

    def test_regular_user_cannot_return_book(self):
        self.client.force_login(self.regular_user)
        url = reverse('library:borrow-return', args=[self.borrow_record.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    # --- Staff and Superuser Allowed Administrative Operations ---

    def test_staff_user_can_access_administrative_views(self):
        self.client.force_login(self.staff_user)
        admin_urls = [
            reverse('library:book-create'),
            reverse('library:book-update', args=[self.book.pk]),
            reverse('library:category-create'),
            reverse('library:category-update', args=[self.category.pk]),
            reverse('library:reader-create'),
            reverse('library:reader-update', args=[self.reader.pk]),
            reverse('library:borrow-issue'),
            reverse('library:borrow-return', args=[self.borrow_record.pk]),
        ]
        for url in admin_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_administrative_views(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('library:book-create'))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('library:borrow-issue'))
        self.assertEqual(response.status_code, 200)


class DjangoAdminAccessTests(TestCase):
    """
    Tests ensuring only staff and superusers can access /admin/.
    Regular authenticated users and unauthenticated guests are denied.
    """
    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular_admin_test",
            password="password123",
            is_staff=False,
        )
        self.staff_user = User.objects.create_user(
            username="staff_admin_test",
            password="password123",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="super_admin_test",
            password="password123",
            email="super@example.com",
        )
        self.admin_url = '/admin/'

    def test_unauthenticated_access_to_admin_redirects_to_admin_login(self):
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_regular_user_cannot_access_django_admin(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(self.admin_url)
        # Django admin redirects non-staff authenticated users to admin login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_user_can_access_django_admin(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site administration')

    def test_superuser_can_access_django_admin(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site administration')


class NavigationAndUITests(TestCase):
    """
    Tests for authentication and permission UI elements:
    - User display name and role badge
    - Logout button
    - Hiding administrative actions from regular users
    """
    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular_ui_user",
            password="password123",
            first_name="John",
            last_name="Patron",
            is_staff=False,
        )
        self.staff_user = User.objects.create_user(
            username="staff_ui_user",
            password="password123",
            first_name="Sara",
            last_name="Librarian",
            is_staff=True,
        )
        self.category = Category.objects.create(name="Fiction")
        self.book = Book.objects.create(
            title="Dune",
            author="Frank Herbert",
            isbn="9780441172719",
            category=self.category,
            total_copies=3,
            available_copies=3,
        )

    def test_navigation_displays_user_name_and_logout_form(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        # Full name John Patron is rendered
        self.assertContains(response, "John Patron")
        # Role badge Patron is rendered
        self.assertContains(response, "badge-patron")
        # Logout button and action
        self.assertContains(response, reverse('core:logout'))
        self.assertContains(response, "Sign Out")

    def test_regular_user_does_not_see_admin_buttons(self):
        self.client.force_login(self.regular_user)

        # On dashboard
        home_res = self.client.get(reverse('core:home'))
        self.assertNotContains(home_res, reverse('library:borrow-issue'))
        self.assertNotContains(home_res, reverse('library:book-create'))
        self.assertNotContains(home_res, reverse('library:category-create'))
        self.assertNotContains(home_res, reverse('library:reader-create'))

        # On book list
        book_res = self.client.get(reverse('library:book-list'))
        self.assertNotContains(book_res, reverse('library:book-create'))
        self.assertNotContains(book_res, reverse('library:book-update', args=[self.book.pk]))
        self.assertNotContains(book_res, reverse('library:book-delete', args=[self.book.pk]))

        # On book detail
        book_detail_res = self.client.get(reverse('library:book-detail', args=[self.book.pk]))
        self.assertNotContains(book_detail_res, reverse('library:book-update', args=[self.book.pk]))
        self.assertNotContains(book_detail_res, reverse('library:book-delete', args=[self.book.pk]))

    def test_staff_user_sees_administrative_action_buttons(self):
        self.client.force_login(self.staff_user)

        # On dashboard
        home_res = self.client.get(reverse('core:home'))
        self.assertContains(home_res, reverse('library:borrow-issue'))
        self.assertContains(home_res, reverse('library:book-create'))
        self.assertContains(home_res, "Sara Librarian")
        self.assertContains(home_res, "badge-staff")

        # On book list
        book_res = self.client.get(reverse('library:book-list'))
        self.assertContains(book_res, reverse('library:book-create'))
        self.assertContains(book_res, reverse('library:book-update', args=[self.book.pk]))
        self.assertContains(book_res, reverse('library:book-delete', args=[self.book.pk]))
