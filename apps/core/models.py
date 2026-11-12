from django.db import models


class TimeStampedModel(models.Model):
    """
    An abstract base model providing self-updating
    created_at and updated_at fields.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the record was created."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the record was last updated."
    )

    class Meta:
        abstract = True
