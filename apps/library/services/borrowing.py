from datetime import timedelta
from typing import Optional, Union

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.library.models import Book, BorrowRecord, Reader


class BorrowingError(ValidationError):
    """Specific exception raised when borrowing or return operations fail business rules."""
    pass


@transaction.atomic
def issue_book(
    book: Union[Book, int],
    reader: Union[Reader, int],
    due_date: Optional[object] = None,
    issue_date: Optional[object] = None,
) -> BorrowRecord:
    """
    Circulation service: Issues a book copy to a reader patron.

    Concurrency and integrity guarantees:
    - Runs within an atomic transaction.
    - Applies `select_for_update()` on the book row to prevent race conditions
      where two concurrent requests might borrow the last remaining copy.
    - Applies `select_for_update()` to verify the reader does not already have
      an active loan for this book.
    - Atomically decrements `available_copies` using an `F()` expression.
    - Validates that copies remain strictly non-negative.
    """
    # 1. Resolve and lock the Book record
    book_id = book.pk if isinstance(book, Book) else int(book)
    try:
        book_obj = Book.objects.select_for_update().get(pk=book_id)
    except Book.DoesNotExist:
        raise BorrowingError("The requested book does not exist.")

    # 2. Resolve and lock the Reader record
    reader_id = reader.pk if isinstance(reader, Reader) else int(reader)
    try:
        reader_obj = Reader.objects.select_for_update().get(pk=reader_id)
    except Reader.DoesNotExist:
        raise BorrowingError("The requested reader does not exist.")

    # 3. Check inventory availability
    if book_obj.available_copies <= 0:
        raise BorrowingError(
            f"No copies of '{book_obj.title}' are currently available for borrowing."
        )

    # 4. Check for active loan of the same book by the same reader
    has_active_loan = (
        BorrowRecord.objects.select_for_update()
        .filter(reader=reader_obj, book=book_obj, status=BorrowRecord.STATUS_ACTIVE)
        .exists()
    )
    if has_active_loan:
        raise BorrowingError(
            f"Reader '{reader_obj.full_name}' already has an active loan for '{book_obj.title}'."
        )

    # 5. Resolve and validate dates
    resolved_issue_date = issue_date or timezone.localdate()
    resolved_due_date = due_date or (resolved_issue_date + timedelta(days=14))

    if resolved_due_date < resolved_issue_date:
        raise BorrowingError("Due date cannot be earlier than the issue date.")

    # 6. Create the BorrowRecord
    record = BorrowRecord(
        book=book_obj,
        reader=reader_obj,
        issue_date=resolved_issue_date,
        due_date=resolved_due_date,
        status=BorrowRecord.STATUS_ACTIVE,
    )
    record.full_clean()
    record.save()

    # 7. Atomically decrement book available copies
    book_obj.available_copies = F("available_copies") - 1
    book_obj.save(update_fields=["available_copies", "updated_at"])
    book_obj.refresh_from_db()

    return record


@transaction.atomic
def return_book(borrow_record_id: int) -> BorrowRecord:
    """
    Circulation service: Returns an actively borrowed book copy.

    Concurrency and integrity guarantees:
    - Runs within an atomic transaction.
    - Resolves book_id and acquires exclusive lock on the Book row FIRST,
      establishing a consistent lock acquisition hierarchy with issue_book()
      to eliminate potential deadlock cycles under high concurrency.
    - Acquires exclusive lock on the BorrowRecord SECOND to prevent double-returns.
    - Atomically increments `available_copies` using an `F()` expression.
    - Ensures `available_copies` never exceeds `total_copies`.
    """
    # 1. Peek at record metadata to identify associated book and current status
    try:
        record_meta = BorrowRecord.objects.values("book_id", "status").get(pk=borrow_record_id)
    except BorrowRecord.DoesNotExist:
        raise BorrowingError("Borrowing record not found.")

    if record_meta["status"] == BorrowRecord.STATUS_RETURNED:
        raise BorrowingError("This borrowing record has already been marked as returned.")

    # 2. Acquire exclusive lock on the Book row FIRST (matching issue_book lock order)
    try:
        book_obj = Book.objects.select_for_update().get(pk=record_meta["book_id"])
    except Book.DoesNotExist:
        raise BorrowingError("The book associated with this record no longer exists.")

    # 3. Acquire exclusive lock on the BorrowRecord SECOND
    record = BorrowRecord.objects.select_for_update().get(pk=borrow_record_id)

    # Re-verify status under the lock in case of concurrent race condition
    if record.status == BorrowRecord.STATUS_RETURNED:
        raise BorrowingError("This borrowing record has already been marked as returned.")

    # 4. Safety boundary check: available copies cannot exceed total copies
    if book_obj.available_copies >= book_obj.total_copies:
        raise BorrowingError(
            f"Cannot return book: available copies ({book_obj.available_copies}) "
            f"is already at maximum capacity ({book_obj.total_copies})."
        )

    # 5. Update the borrowing record
    record.status = BorrowRecord.STATUS_RETURNED
    record.returned_at = timezone.now()
    record.save(update_fields=["status", "returned_at", "updated_at"])

    # 6. Atomically increment book available copies
    book_obj.available_copies = F("available_copies") + 1
    book_obj.save(update_fields=["available_copies", "updated_at"])
    book_obj.refresh_from_db()

    return record
