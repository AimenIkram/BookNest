from django import forms
from django.core.exceptions import ValidationError

from .models import Book, Category, Reader
from .validators import (
    normalize_isbn,
    validate_isbn,
    validate_phone_number,
    validate_publication_date,
)


class CategoryForm(forms.ModelForm):
    """
    Form for creating and updating Category instances with strict
    whitespace trimming and case-insensitive duplicate validation.
    """
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Computer Science, Fiction',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional summary of this book category...',
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Category name cannot be empty or whitespace only.")

        # Case-insensitive duplicate check
        qs = Category.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError(f"A category with the name '{name}' already exists.")

        return name

    def clean_description(self):
        return self.cleaned_data.get('description', '').strip()


class BookForm(forms.ModelForm):
    """
    Form for creating and updating Book records with ISBN normalization,
    publication date verification, and available-copies cross-field validation.
    """
    class Meta:
        model = Book
        fields = [
            'title',
            'author',
            'isbn',
            'category',
            'total_copies',
            'available_copies',
            'publication_date',
            'description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Book title',
            }),
            'author': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Author(s) name',
            }),
            'isbn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 978-0-13-449416-6 or 0134494164 (optional)',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control form-select',
            }),
            'total_copies': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'available_copies': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'publication_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional synopsis or summary...',
            }),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise ValidationError("Title cannot be empty or whitespace only.")
        return title

    def clean_author(self):
        author = self.cleaned_data.get('author', '').strip()
        if not author:
            raise ValidationError("Author cannot be empty or whitespace only.")
        return author

    def clean_isbn(self):
        raw_isbn = self.cleaned_data.get('isbn')
        cleaned_isbn = normalize_isbn(raw_isbn)

        if cleaned_isbn:
            # Validate format (10 or 13 digits)
            validate_isbn(cleaned_isbn)

            # Check uniqueness against other books
            qs = Book.objects.filter(isbn=cleaned_isbn)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(f"A book with ISBN '{cleaned_isbn}' already exists.")

            return cleaned_isbn

        return None

    def clean_publication_date(self):
        pub_date = self.cleaned_data.get('publication_date')
        if pub_date:
            validate_publication_date(pub_date)
        return pub_date

    def clean_total_copies(self):
        total = self.cleaned_data.get('total_copies')
        if total is not None and total < 0:
            raise ValidationError("Total copies cannot be negative.")
        return total

    def clean_available_copies(self):
        avail = self.cleaned_data.get('available_copies')
        if avail is not None and avail < 0:
            raise ValidationError("Available copies cannot be negative.")
        return avail

    def clean_description(self):
        return self.cleaned_data.get('description', '').strip()

    def clean(self):
        cleaned_data = super().clean()
        total_copies = cleaned_data.get('total_copies')
        available_copies = cleaned_data.get('available_copies')

        if total_copies is not None and available_copies is not None:
            if available_copies > total_copies:
                self.add_error(
                    'available_copies',
                    "Available copies cannot exceed total copies."
                )
        return cleaned_data


class ReaderForm(forms.ModelForm):
    """
    Form for registering and updating library readers with name validation,
    email normalization (lowercased, empty to None), and phone format checking.
    """
    class Meta:
        model = Reader
        fields = ['full_name', 'email', 'phone', 'address']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full legal or preferred name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'name@example.com (optional)',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., +1-555-0199 or 03001234567 (optional)',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional mailing or residential address...',
            }),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not full_name:
            raise ValidationError("Full name cannot be empty or whitespace only.")
        if len(full_name) < 2:
            raise ValidationError("Full name must be at least 2 characters long.")
        return full_name

    def clean_email(self):
        """
        Normalize email: strip, lowercase, and convert empty/whitespace-only to None.
        Enforces case-insensitive uniqueness check.
        """
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip().lower()
            if not email:
                return None

            qs = Reader.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(f"A reader with email '{email}' is already registered.")

            return email
        return None

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            validate_phone_number(phone)
            return phone
        return ""

    def clean_address(self):
        return self.cleaned_data.get('address', '').strip()
