"""Serializers for the BMAD domain: projects, artifacts, epics, stories, versions."""
from rest_framework import serializers

from apps.artifacts.models import Artifact, Attachment
from apps.core.models import Version
from apps.projects.models import CoreConfig, Project, SprintStatus
from apps.workflow.models import Epic, Story


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = (
            "id", "organization", "team", "owner", "name", "slug", "description",
            "created_at",
        )
        read_only_fields = ("owner", "slug", "created_at")


class CoreConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoreConfig
        fields = ("id", "project", "data")
        read_only_fields = ("project",)


class SprintStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SprintStatus
        fields = ("id", "project", "data")
        read_only_fields = ("project",)


class VersionSerializer(serializers.ModelSerializer):
    """Compact representation for version listings."""

    class Meta:
        model = Version
        fields = ("number", "message", "author", "created_at")


class VersionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version
        fields = ("number", "message", "author", "created_at", "body", "data")


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ("id", "file", "uploaded_by", "created_at")
        read_only_fields = ("uploaded_by", "created_at")


class ArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = (
            "id", "project", "type", "title", "slug", "status", "body", "data",
            "target_story", "current_version", "created_by", "created_at", "updated_at",
        )
        read_only_fields = ("slug", "current_version", "created_by", "created_at", "updated_at")


class EpicSerializer(serializers.ModelSerializer):
    story_count = serializers.IntegerField(source="stories.count", read_only=True)

    class Meta:
        model = Epic
        fields = (
            "id", "project", "number", "title", "goal", "status", "body", "data",
            "story_count", "created_by", "created_at",
        )
        # number is assigned server-side (auto-incremented within the project).
        read_only_fields = ("number", "created_by", "created_at")


class StorySerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = Story
        fields = (
            "id", "epic", "number", "label", "title", "status",
            "acceptance_criteria", "tasks", "dev_notes", "qa_results",
            "body", "data", "assignee", "current_version",
            "created_by", "created_at", "updated_at",
        )
        # number is assigned server-side (auto-incremented within the epic);
        # status changes only through the /transition/ endpoint.
        read_only_fields = (
            "number", "status", "label", "current_version", "created_by",
            "created_at", "updated_at",
        )


class StoryTransitionSerializer(serializers.Serializer):
    to = serializers.ChoiceField(choices=[s for s, _ in Story._meta.get_field("status").choices])
