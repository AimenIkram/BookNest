from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    """
    Represents a genre or literary classification for books.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique name of the book category/genre."
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of the category."
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Book(TimeStampedModel):
    """
    Represents a book title and its inventory in the library.
    """
    title = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Title of the book."
    )
    author = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Author(s) of the book."
    )
    isbn = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="International Standard Book Number (optional, unique)."
    )
    description = models.TextField(
        blank=True,
        help_text="Synopsis or summary of the book."
    )
    publication_date = models.DateField(
        null=True,
        blank=True,
        help_text="Official publication date."
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="books",
        help_text="Genre/category this book belongs to."
    )
    total_copies = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Total number of copies owned by the library."
    )
    available_copies = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="Number of copies currently available on shelves."
    )

    class Meta:
        verbose_name = "Book"
        verbose_name_plural = "Books"
        ordering = ["title", "author"]
        constraints = [
            models.CheckConstraint(
                condition=Q(available_copies__lte=F("total_copies")),
                name="book_available_copies_lte_total_copies",
            )
        ]

    def clean(self):
        super().clean()
        if self.available_copies is not None and self.total_copies is not None:
            if self.available_copies > self.total_copies:
                raise ValidationError({
                    "available_copies": "Available copies cannot exceed total copies."
                })

    def __str__(self) -> str:
        return f"{self.title} by {self.author}"


class Reader(TimeStampedModel):
    """
    Represents a registered library patron.
    """
    full_name = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Full legal or preferred name of the reader."
    )
    email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
        help_text="Primary email address (optional, unique)."
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number."
    )
    address = models.TextField(
        blank=True,
        help_text="Residential or mailing address."
    )

    class Meta:
        verbose_name = "Reader"
        verbose_name_plural = "Readers"
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name
