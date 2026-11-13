"""
Authorization mixins and decorators for BookNest.
Enforces role-based access control based on Django's built-in User model
and its `is_staff` / `is_superuser` privileges.
"""
from functools import wraps

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class StaffRequiredMixin(UserPassesTestMixin):
    """
    CBV mixin that restricts access strictly to staff members or superusers.
    - Unauthenticated requests: Redirected to LOGIN_URL with preserved ?next= parameter.
    - Authenticated non-staff (regular) users: Denied with HTTP 403 (PermissionDenied).
    - Staff / superusers: Allowed access to execute administrative operations.
    """
    permission_denied_message = "Administrative staff privileges are required to perform this action."

    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def staff_required(view_func):
    """
    FBV decorator that restricts access strictly to staff members or superusers.
    - Unauthenticated requests: Redirected to login with ?next=.
    - Authenticated non-staff users: Raised PermissionDenied (HTTP 403).
    - Staff / superusers: Allowed to execute the view.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Administrative staff privileges are required to perform this action.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
