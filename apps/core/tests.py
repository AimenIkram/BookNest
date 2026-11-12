from django.test import TestCase, SimpleTestCase
from django.urls import reverse, resolve
from apps.core.views import home_view


class HomePageTests(SimpleTestCase):
    """
    Tests for the BookNest core home view and template inheritance.
    SimpleTestCase is used because this does not touch the database yet.
    """

    def setUp(self):
        self.url = reverse('core:home')
        self.response = self.client.get(self.url)

    def test_home_page_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_home_page_template_used(self):
        self.assertTemplateUsed(self.response, 'core/home.html')
        self.assertTemplateUsed(self.response, 'base.html')

    def test_home_page_contains_expected_content(self):
        self.assertContains(self.response, 'BookNest Management System')
        self.assertContains(self.response, 'Phase 02')
        self.assertContains(self.response, 'Decoupled Configuration')

    def test_home_url_resolves_correctly(self):
        resolved = resolve('/')
        self.assertEqual(resolved.func, home_view)
        self.assertEqual(resolved.namespace, 'core')
