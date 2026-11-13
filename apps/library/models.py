from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

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


class BorrowRecord(TimeStampedModel):
    """
    Represents the circulation loan of a book copy to a registered reader patron.
    Tracks issuance, due date, return timestamp, and operational status.
    """
    STATUS_ACTIVE = "ACTIVE"
    STATUS_RETURNED = "RETURNED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETURNED, "Returned"),
    ]

    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="borrow_records",
        help_text="The book copy being borrowed."
    )
    reader = models.ForeignKey(
        Reader,
        on_delete=models.PROTECT,
        related_name="borrow_records",
        help_text="The reader patron who borrowed the book."
    )
    issue_date = models.DateField(
        default=timezone.localdate,
        help_text="Date on which the book was issued."
    )
    due_date = models.DateField(
        help_text="Date by which the book must be returned."
    )
    returned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Exact timestamp when the book was returned."
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
        help_text="Current borrowing status (Active or Returned)."
    )

    class Meta:
        verbose_name = "Borrow Record"
        verbose_name_plural = "Borrow Records"
        ordering = ["-issue_date", "-id"]
        indexes = [
            models.Index(fields=["status", "due_date"], name="borrow_status_due_idx"),
            models.Index(fields=["reader", "status"], name="borrow_reader_status_idx"),
            models.Index(fields=["book", "status"], name="borrow_book_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(due_date__gte=F("issue_date")),
                name="borrow_due_date_gte_issue_date",
            )
        ]

    @property
    def is_overdue(self) -> bool:
        """
        Dynamically calculates whether the borrowing record is currently overdue.
        Overdue records are active loans whose due_date is earlier than today's date.
        """
        return self.status == self.STATUS_ACTIVE and self.due_date < timezone.localdate()

    def clean(self):
        super().clean()
        if self.issue_date and self.due_date:
            if self.due_date < self.issue_date:
                raise ValidationError({
                    "due_date": "Due date cannot be earlier than the issue date."
                })

        # Prevent duplicate active borrowing for the same reader and book
        if self.status == self.STATUS_ACTIVE and self.book_id and self.reader_id:
            qs = BorrowRecord.objects.filter(
                reader_id=self.reader_id,
                book_id=self.book_id,
                status=self.STATUS_ACTIVE,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "This reader already has an active borrowing record for this book."
                )

    def __str__(self) -> str:
        return f"'{self.book.title}' borrowed by {self.reader.full_name} [{self.status}]"
