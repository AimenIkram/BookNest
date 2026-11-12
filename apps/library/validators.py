import datetime
import re
from django.core.exceptions import ValidationError


def normalize_isbn(value: str) -> str | None:
    """
    Strips hyphens and whitespace from an ISBN string and converts to uppercase.
    Returns None if the resulting string is empty.
    """
    if not value:
        return None
    cleaned = re.sub(r'[-\s]', '', str(value)).strip().upper()
    return cleaned if cleaned else None


def validate_isbn(value: str) -> None:
    """
    Validates that a provided ISBN conforms to standard ISBN-10 or ISBN-13 format.
    Hyphens and spaces are permitted before normalization.
    """
    if not value:
        return

    cleaned = normalize_isbn(value)
    if not cleaned:
        return

    # Check ISBN-10 format: 9 digits followed by a digit or 'X'
    if len(cleaned) == 10:
        if not (cleaned[:9].isdigit() and (cleaned[9].isdigit() or cleaned[9] == 'X')):
            raise ValidationError(
                "Invalid ISBN-10 format. An ISBN-10 must contain 9 digits followed by a digit or 'X'."
            )
        return

    # Check ISBN-13 format: 13 digits
    if len(cleaned) == 13:
        if not cleaned.isdigit():
            raise ValidationError(
                "Invalid ISBN-13 format. An ISBN-13 must consist of exactly 13 digits."
            )
        return

    raise ValidationError(
        "Invalid ISBN length. An ISBN must be either 10 or 13 digits (hyphens and spaces are allowed)."
    )


def validate_phone_number(value: str) -> None:
    """
    Validates telephone number strings. Accepts standard international
    or domestic formats (e.g., +1-555-0199, (555) 019-2834, +44 20 7946 0919).
    Requires between 7 and 15 digits.
    """
    if not value:
        return

    trimmed = value.strip()
    if not trimmed:
        return

    # Pattern allowing optional leading +, followed by digits, spaces, parentheses, hyphens, and dots
    phone_pattern = r'^\+?[0-9\s\(\)\-\.]{7,25}$'
    if not re.match(phone_pattern, trimmed):
        raise ValidationError(
            "Enter a valid phone number (e.g., +1-555-0199, (555) 019-2834, or 03001234567)."
        )

    # Extract only digit characters to ensure valid length
    digits = re.sub(r'\D', '', trimmed)
    if len(digits) < 7 or len(digits) > 15:
        raise ValidationError(
            f"Phone number must contain between 7 and 15 digits (found {len(digits)})."
        )


def validate_publication_date(value: datetime.date) -> None:
    """
    Ensures the publication date is not in the future.
    """
    if not value:
        return

    today = datetime.date.today()
    if value > today:
        raise ValidationError(
            f"Publication date cannot be in the future (today is {today.strftime('%b %d, %Y')})."
        )
