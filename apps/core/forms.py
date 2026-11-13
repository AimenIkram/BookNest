"""
Authentication and core forms for BookNest.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm


class BookNestLoginForm(AuthenticationForm):
    """
    Customized Django AuthenticationForm styled with BookNest UI conventions.
    """
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username",
                "autofocus": True,
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )
