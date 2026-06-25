"""Artifacts: the generic, versioned BMAD document store.

Epics and Stories are promoted to first-class models in ``apps.workflow``; everything
else (brief, prd, architecture, ux_spec, research, brainstorm, qa_gate, …) lives here
as an ``Artifact`` with type-specific structure in ``data`` (see docs/DATA_SCHEMAS.md).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.accounts.models import UUIDModel
from apps.core.models import Version, Versioned
from apps.projects.models import Project


class ArtifactType(models.TextChoices):
    BRIEF = "brief", "Project Brief"
    RESEARCH = "research", "Research"
    BRAINSTORM = "brainstorm", "Brainstorming"
    PRD = "prd", "PRD"
    UX_SPEC = "ux_spec", "UX / Front-end Spec"
    ARCHITECTURE = "architecture", "Architecture"
    QA_GATE = "qa_gate", "QA Gate"
    OTHER = "other", "Other"


class ArtifactStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_REVIEW = "in_review", "In Review"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class Artifact(UUIDModel, Versioned):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="artifacts"
    )
    type = models.CharField(max_length=20, choices=ArtifactType.choices)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, blank=True)
    status = models.CharField(
        max_length=20, choices=ArtifactStatus.choices, default=ArtifactStatus.DRAFT
    )
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_artifacts",
    )
    current_version = models.ForeignKey(
        Version, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # When type == qa_gate, the Story this gate assesses (string ref avoids a cycle).
    target_story = models.ForeignKey(
        "workflow.Story", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="qa_gates",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "type"])]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "slug"],
                condition=~models.Q(slug=""),
                name="uniq_artifact_slug_per_project",
            )
        ]

    def __str__(self) -> str:
        return f"[{self.type}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            self.slug = slugify(self.title)[:320]
        super().save(*args, **kwargs)

    @property
    def organization_id(self):
        return self.project.organization_id


class Attachment(UUIDModel):
    artifact = models.ForeignKey(
        Artifact, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="attachments/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    def __str__(self) -> str:
        return self.file.name
