"""
Integration test verifying concurrent row-level locking on live MySQL 8.0.46.
Uses separate threads with independent database connections and barrier synchronization.
"""
import os
import sys
import threading
from datetime import timedelta

import django

# Setup Django environment pointing to live MySQL
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connections
from django.utils import timezone
from apps.library.models import Book, BorrowRecord, Category, Reader
from apps.library.services.borrowing import BorrowingError, issue_book, return_book


def run_concurrency_test():
    print("=" * 60)
    print("STARTING LIVE MYSQL CONCURRENCY INTEGRATION TEST")
    print("Target DB: MySQL 8.0.46 (InnoDB)")
    print("=" * 60)

    # 1. Setup isolated test data
    category, _ = Category.objects.get_or_create(
        name="[Concurrency Test Category]",
        defaults={"description": "Temporary category for concurrency verification"},
    )
    book = Book.objects.create(
        title="[Concurrency Test Book]",
        author="Concurrency Tester",
        category=category,
        total_copies=1,
        available_copies=1,  # ONLY 1 COPY AVAILABLE
    )
    reader1 = Reader.objects.create(
        full_name="Concurrent Reader Alpha",
        email="concurrent.alpha@test.com",
    )
    reader2 = Reader.objects.create(
        full_name="Concurrent Reader Beta",
        email="concurrent.beta@test.com",
    )

    print(f"Created test book '{book.title}' with total_copies=1, available_copies=1.")
    print("Simulating 2 concurrent threads attempting to issue the LAST available copy simultaneously...")

    # Barrier to ensure both threads invoke issue_book at the exact same instant
    barrier = threading.Barrier(2)
    results = {"thread1": None, "thread2": None}
    errors = {"thread1": None, "thread2": None}

    def worker_issue(thread_name, reader_id):
        # Close old connection to ensure thread opens its own separate MySQL socket
        connections.close_all()
        try:
            barrier.wait(timeout=5)
            record = issue_book(book=book.pk, reader=reader_id)
            results[thread_name] = record
        except Exception as e:
            errors[thread_name] = e
        finally:
            connections.close_all()

    t1 = threading.Thread(target=worker_issue, args=("thread1", reader1.pk))
    t2 = threading.Thread(target=worker_issue, args=("thread2", reader2.pk))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Close connections on main thread and refresh
    connections.close_all()
    book.refresh_from_db()

    print("\n--- TEST 1 RESULTS: CONCURRENT ISSUANCE OF LAST COPY ---")
    print(f"Thread 1 Result: {'SUCCESS (Issued #' + str(results['thread1'].pk) + ')' if results['thread1'] else 'REJECTED: ' + str(errors['thread1'])}")
    print(f"Thread 2 Result: {'SUCCESS (Issued #' + str(results['thread2'].pk) + ')' if results['thread2'] else 'REJECTED: ' + str(errors['thread2'])}")
    print(f"Book available copies in MySQL: {book.available_copies}")

    # Verification: Exactly one succeeded, one failed with BorrowingError, copies is 0
    success_count = sum(1 for r in results.values() if r is not None)
    error_count = sum(1 for e in errors.values() if isinstance(e, BorrowingError))

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert error_count == 1, f"Expected exactly 1 BorrowingError, got {error_count}"
    assert book.available_copies == 0, f"Expected 0 available copies, got {book.available_copies}"

    active_record = results["thread1"] or results["thread2"]
    print(">>> PASS: Simultaneous issue requests successfully serialized by row-lock. No overselling!")

    # 2. Test Concurrent Return of the same record
    print("\n" + "=" * 60)
    print("Simulating 2 concurrent threads attempting to return the SAME borrowing record simultaneously...")
    return_barrier = threading.Barrier(2)
    return_results = {"thread1": None, "thread2": None}
    return_errors = {"thread1": None, "thread2": None}

    def worker_return(thread_name, record_id):
        connections.close_all()
        try:
            return_barrier.wait(timeout=5)
            record = return_book(borrow_record_id=record_id)
            return_results[thread_name] = record
        except Exception as e:
            return_errors[thread_name] = e
        finally:
            connections.close_all()

    rt1 = threading.Thread(target=worker_return, args=("thread1", active_record.pk))
    rt2 = threading.Thread(target=worker_return, args=("thread2", active_record.pk))

    rt1.start()
    rt2.start()
    rt1.join()
    rt2.join()

    connections.close_all()
    book.refresh_from_db()
    active_record.refresh_from_db()

    print("\n--- TEST 2 RESULTS: CONCURRENT RETURN OF SAME RECORD ---")
    print(f"Thread 1 Result: {'SUCCESS (Returned)' if return_results['thread1'] else 'REJECTED: ' + str(return_errors['thread1'])}")
    print(f"Thread 2 Result: {'SUCCESS (Returned)' if return_results['thread2'] else 'REJECTED: ' + str(return_errors['thread2'])}")
    print(f"Book available copies in MySQL: {book.available_copies}")
    print(f"BorrowRecord status in MySQL: {active_record.status}")

    return_success_count = sum(1 for r in return_results.values() if r is not None)
    return_error_count = sum(1 for e in return_errors.values() if isinstance(e, BorrowingError))

    assert return_success_count == 1, f"Expected exactly 1 return success, got {return_success_count}"
    assert return_error_count == 1, f"Expected exactly 1 return error, got {return_error_count}"
    assert book.available_copies == 1, f"Expected 1 available copy, got {book.available_copies}"

    print(">>> PASS: Simultaneous return requests successfully serialized by row-lock. No double increment!")

    # 3. Clean up test data
    BorrowRecord.objects.filter(pk=active_record.pk).delete()
    book.delete()
    reader1.delete()
    reader2.delete()
    category.delete()
    print("\nTest data cleanly removed from MySQL booknest_db.")
    print("=" * 60)
    print("ALL MYSQL CONCURRENCY CHECKS PASSED RIGOROUSLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_concurrency_test()
