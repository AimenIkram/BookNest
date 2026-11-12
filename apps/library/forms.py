from django import forms
from .models import Book, Category, Reader


class CategoryForm(forms.ModelForm):
    """
    Form for creating and updating Category instances.
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


class BookForm(forms.ModelForm):
    """
    Form for creating and updating Book records.
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
                'placeholder': 'e.g., 9780134494166 (optional)',
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
    Form for registering and updating library readers.
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
                'placeholder': 'Contact phone number (optional)',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional mailing or residential address...',
            }),
        }

    def clean_email(self):
        """
        Normalize empty/whitespace-only email to None to avoid violating
        MySQL unique constraint with multiple empty string values.
        """
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip()
            if not email:
                return None
            return email
        return None
