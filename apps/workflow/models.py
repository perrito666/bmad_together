"""Workflow: Epics and Stories — the first-class, lifecycle-bearing artifacts.

Stories carry a validated status state machine (see docs/DATA_SCHEMAS.md).
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import UUIDModel
from apps.core.models import Version, Versioned
from apps.projects.models import Project


class Epic(UUIDModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="epics")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    goal = models.TextField(blank=True)
    status = models.CharField(max_length=30, default="planned")
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_epics",
    )

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["project", "number"], name="uniq_epic_number")
        ]

    def __str__(self) -> str:
        return f"Epic {self.number}: {self.title}"

    @property
    def organization_id(self):
        return self.project.organization_id


class StoryStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    IN_PROGRESS = "in_progress", "In Progress"
    REVIEW = "review", "Review"
    DONE = "done", "Done"
    BLOCKED = "blocked", "Blocked"


# Allowed status transitions (see docs/DATA_SCHEMAS.md state machine).
STORY_TRANSITIONS: dict[str, set[str]] = {
    StoryStatus.DRAFT: {StoryStatus.APPROVED},
    StoryStatus.APPROVED: {StoryStatus.IN_PROGRESS},
    StoryStatus.IN_PROGRESS: {StoryStatus.REVIEW, StoryStatus.BLOCKED},
    StoryStatus.REVIEW: {StoryStatus.DONE, StoryStatus.IN_PROGRESS, StoryStatus.BLOCKED},
    StoryStatus.BLOCKED: {StoryStatus.IN_PROGRESS},
    StoryStatus.DONE: set(),
}


class InvalidTransition(ValidationError):
    pass


class Story(UUIDModel, Versioned):
    epic = models.ForeignKey(Epic, on_delete=models.CASCADE, related_name="stories")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    status = models.CharField(
        max_length=20, choices=StoryStatus.choices, default=StoryStatus.DRAFT
    )
    acceptance_criteria = models.JSONField(default=list, blank=True)
    tasks = models.JSONField(default=list, blank=True)
    dev_notes = models.TextField(blank=True)
    qa_results = models.JSONField(default=dict, blank=True)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_stories",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_stories",
    )
    current_version = models.ForeignKey(
        Version, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["epic__number", "number"]
        constraints = [
            models.UniqueConstraint(fields=["epic", "number"], name="uniq_story_number")
        ]

    def __str__(self) -> str:
        return f"Story {self.label}: {self.title}"

    @property
    def label(self) -> str:
        return f"{self.epic.number}.{self.number}"

    @property
    def organization_id(self):
        return self.epic.project.organization_id

    @property
    def all_tasks_done(self) -> bool:
        tasks = self.tasks or []
        return all(t.get("done") for t in tasks) if tasks else True

    def can_transition_to(self, target: str) -> bool:
        return target in STORY_TRANSITIONS.get(self.status, set())

    def transition_to(self, target: str, *, enforce_tasks: bool = True, save: bool = True):
        """Move to ``target`` if the state machine allows it, else raise."""
        if not self.can_transition_to(target):
            raise InvalidTransition(
                f"Cannot move story {self.label} from '{self.status}' to '{target}'."
            )
        if target == StoryStatus.DONE and enforce_tasks and not self.all_tasks_done:
            raise InvalidTransition(
                f"Story {self.label} has incomplete tasks; cannot mark done."
            )
        self.status = target
        if save:
            self.save(update_fields=["status", "updated_at"])
        return self
