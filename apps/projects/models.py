"""Projects: a BMAD workspace that owns all artifacts, plus its CoreConfig."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.accounts.models import Organization, Team, UUIDModel


def default_core_config() -> dict:
    """Mirror of BMAD's core-config.yaml defaults."""
    return {
        "prd": {"file": "docs/prd.md", "sharded": True, "epics_glob": "docs/prd/epic-*.md"},
        "architecture": {"file": "docs/architecture.md", "sharded": True},
        "stories": {"location": "docs/stories"},
        "qa": {"location": "docs/qa"},
        "dev_load_always_files": ["docs/architecture/coding-standards.md"],
        "markdown_exploder": True,
    }


class Project(UUIDModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="projects"
    )
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, related_name="projects", null=True, blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="owned_projects",
        null=True,
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="uniq_project_slug_per_org"
            )
        ]

    def __str__(self) -> str:
        return f"{self.organization.slug}/{self.slug}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class CoreConfig(UUIDModel):
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="config"
    )
    data = models.JSONField(default=default_core_config, blank=True)

    def __str__(self) -> str:
        return f"config for {self.project}"

    @property
    def organization_id(self):
        return self.project.organization_id


class SprintStatus(UUIDModel):
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="sprint_status"
    )
    data = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"sprint-status for {self.project}"

    @property
    def organization_id(self):
        return self.project.organization_id
