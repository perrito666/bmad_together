"""Shared building blocks: generic immutable versioning.

``Version`` snapshots an object's ``body`` + ``data`` on each meaningful save. It
attaches generically so both ``Artifact`` and ``Story`` reuse one history table.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Max

from apps.accounts.models import UUIDModel


class Version(UUIDModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    source = GenericForeignKey("content_type", "object_id")

    number = models.PositiveIntegerField()
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "number"], name="uniq_version_number"
            )
        ]

    def __str__(self) -> str:
        return f"{self.content_type.model}:{self.object_id} v{self.number}"


class Versioned(models.Model):
    """Mixin for models that carry ``body`` + ``data`` and want version history."""

    versions = GenericRelation(Version)

    class Meta:
        abstract = True

    def snapshot(self, *, author=None, message: str = "") -> Version:
        """Append an immutable snapshot of the current ``body``/``data``."""
        next_number = (self.versions.aggregate(m=Max("number"))["m"] or 0) + 1
        version = Version.objects.create(
            source=self,
            number=next_number,
            body=getattr(self, "body", "") or "",
            data=getattr(self, "data", {}) or {},
            author=author,
            message=message,
        )
        # Track the latest snapshot when the model exposes a current_version FK.
        if hasattr(self, "current_version_id"):
            type(self).objects.filter(pk=self.pk).update(current_version=version)
            self.current_version = version
        return version
