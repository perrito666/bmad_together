"""Tenant-scoped REST viewsets for the BMAD domain (milestone 3)."""
from __future__ import annotations

import difflib
import io
import json
import zipfile

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import ROLE_RANK, Role
from apps.accounts.scoping import RolePermission, TenantScopedQuerysetMixin, user_role_in_org
from apps.artifacts.models import Artifact
from apps.projects.models import CoreConfig, Project, SprintStatus
from apps.workflow.models import Epic, InvalidTransition, Story, StoryStatus

from .domain_serializers import (
    ArtifactSerializer,
    CoreConfigSerializer,
    EpicSerializer,
    ProjectSerializer,
    SprintStatusSerializer,
    StorySerializer,
    StoryTransitionSerializer,
    VersionDetailSerializer,
    VersionSerializer,
)


class TenantScopedModelViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, RolePermission]

    def require_role(self, org_id, required=Role.MEMBER):
        role = user_role_in_org(self.request.user, org_id)
        if role is None or ROLE_RANK[role] < ROLE_RANK[required]:
            raise PermissionDenied("Insufficient role for this action.")

    def _paginated(self, queryset, serializer_cls):
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(serializer_cls(page, many=True).data)
        return Response(serializer_cls(queryset, many=True).data)


class ProjectViewSet(TenantScopedModelViewSet):
    serializer_class = ProjectSerializer
    queryset = Project.objects.select_related("organization", "team", "owner")
    org_lookup = "organization_id"

    def get_queryset(self):
        qs = super().get_queryset()
        if org := self.request.query_params.get("org"):
            qs = qs.filter(organization_id=org)
        if team := self.request.query_params.get("team"):
            qs = qs.filter(team_id=team)
        return qs

    def perform_create(self, serializer):
        org = serializer.validated_data["organization"]
        self.require_role(org.id, Role.MEMBER)
        project = serializer.save(owner=self.request.user)
        # Convenience: every project starts with a CoreConfig + SprintStatus.
        CoreConfig.objects.get_or_create(project=project)
        SprintStatus.objects.get_or_create(project=project)

    # --- nested config / sprint-status ---
    @action(detail=True, methods=["get", "put"])
    def config(self, request, pk=None):
        project = self.get_object()
        cfg, _ = CoreConfig.objects.get_or_create(project=project)
        if request.method == "PUT":
            ser = CoreConfigSerializer(cfg, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        return Response(CoreConfigSerializer(cfg).data)

    @action(detail=True, methods=["get"], url_path="sprint-status")
    def sprint_status(self, request, pk=None):
        project = self.get_object()
        sprint, _ = SprintStatus.objects.get_or_create(project=project)
        return Response(SprintStatusSerializer(sprint).data)

    # --- nested artifacts / epics ---
    @action(detail=True, methods=["get", "post"])
    def artifacts(self, request, pk=None):
        project = self.get_object()
        if request.method == "GET":
            qs = project.artifacts.all()
            if t := request.query_params.get("type"):
                qs = qs.filter(type=t)
            if s := request.query_params.get("status"):
                qs = qs.filter(status=s)
            return self._paginated(qs, ArtifactSerializer)
        self.require_role(project.organization_id, Role.MEMBER)
        ser = ArtifactSerializer(data={**request.data, "project": str(project.id)})
        ser.is_valid(raise_exception=True)
        artifact = ser.save(created_by=request.user)
        artifact.snapshot(author=request.user, message="created")
        return Response(ArtifactSerializer(artifact).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def epics(self, request, pk=None):
        project = self.get_object()
        if request.method == "GET":
            return self._paginated(project.epics.all(), EpicSerializer)
        self.require_role(project.organization_id, Role.MEMBER)
        ser = EpicSerializer(data={**request.data, "project": str(project.id)})
        ser.is_valid(raise_exception=True)
        ser.save(created_by=request.user, number=_next_number(project.epics.all()))
        return Response(ser.data, status=status.HTTP_201_CREATED)

    # --- BMAD docs/ round-trip ---
    @action(detail=True, methods=["post"], url_path="import")
    def import_docs(self, request, pk=None):
        from apps.projects.bmad_io import import_tree

        project = self.get_object()
        self.require_role(project.organization_id, Role.MEMBER)
        if "file" in request.FILES:
            files = _unzip(request.FILES["file"].read())
        elif isinstance(request.data.get("files"), dict):
            files = request.data["files"]
        else:
            raise ValidationError("Provide a 'file' (zip upload) or a 'files' mapping.")
        summary = import_tree(project, files, author=request.user)
        return Response(summary.as_dict())

    @action(detail=True, methods=["get"], url_path="export")
    def export_docs(self, request, pk=None):
        from apps.projects.bmad_io import export_tree

        project = self.get_object()
        files = export_tree(project)
        if request.query_params.get("format") == "json":
            return Response({"files": files})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in files.items():
                zf.writestr(path, content)
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="{project.slug}-bmad-docs.zip"'
        return resp

    @action(detail=True, methods=["post"], url_path="next-story")
    def next_story(self, request, pk=None):
        """The next story to pick up: first non-done story in epic/story order."""
        project = self.get_object()
        story = (
            Story.objects.filter(epic__project=project)
            .exclude(status=StoryStatus.DONE)
            .order_by("epic__number", "number")
            .first()
        )
        if story is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(StorySerializer(story).data)


class ArtifactViewSet(TenantScopedModelViewSet):
    serializer_class = ArtifactSerializer
    queryset = Artifact.objects.select_related("project")
    org_lookup = "project__organization_id"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if project := params.get("project"):
            qs = qs.filter(project_id=project)
        if t := params.get("type"):
            qs = qs.filter(type=t)
        if s := params.get("status"):
            qs = qs.filter(status=s)
        if q := params.get("q"):
            qs = qs.filter(title__icontains=q)
        return qs

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        self.require_role(project.organization_id, Role.MEMBER)
        artifact = serializer.save(created_by=self.request.user)
        artifact.snapshot(author=self.request.user, message="created")

    def perform_update(self, serializer):
        artifact = serializer.save()
        artifact.snapshot(author=self.request.user, message="updated")

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        return self._paginated(self.get_object().versions.all(), VersionSerializer)

    @action(detail=True, methods=["get"], url_path=r"versions/(?P<number>\d+)")
    def version_at(self, request, pk=None, number=None):
        version = self.get_object().versions.filter(number=number).first()
        if version is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(VersionDetailSerializer(version).data)

    @action(detail=True, methods=["get"])
    def diff(self, request, pk=None):
        obj = self.get_object()
        try:
            a = obj.versions.get(number=request.query_params["from"])
            b = obj.versions.get(number=request.query_params["to"])
        except (KeyError, obj.versions.model.DoesNotExist) as exc:
            raise ValidationError("Provide valid 'from' and 'to' version numbers.") from exc
        return Response({"body": _diff(a, b, "body"), "data": _diff(a, b, "data")})


class EpicViewSet(TenantScopedModelViewSet):
    serializer_class = EpicSerializer
    queryset = Epic.objects.select_related("project")
    org_lookup = "project__organization_id"

    def get_queryset(self):
        qs = super().get_queryset()
        if project := self.request.query_params.get("project"):
            qs = qs.filter(project_id=project)
        return qs

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        self.require_role(project.organization_id, Role.MEMBER)
        serializer.save(created_by=self.request.user, number=_next_number(project.epics.all()))

    @action(detail=True, methods=["get", "post"])
    def stories(self, request, pk=None):
        epic = self.get_object()
        if request.method == "GET":
            return self._paginated(epic.stories.all(), StorySerializer)
        self.require_role(epic.organization_id, Role.MEMBER)
        ser = StorySerializer(data={**request.data, "epic": str(epic.id)})
        ser.is_valid(raise_exception=True)
        story = ser.save(created_by=request.user, number=_next_number(epic.stories.all()))
        story.snapshot(author=request.user, message="created")
        return Response(StorySerializer(story).data, status=status.HTTP_201_CREATED)


class StoryViewSet(TenantScopedModelViewSet):
    serializer_class = StorySerializer
    queryset = Story.objects.select_related("epic", "epic__project", "assignee")
    org_lookup = "epic__project__organization_id"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if epic := params.get("epic"):
            qs = qs.filter(epic_id=epic)
        if assignee := params.get("assignee"):
            qs = qs.filter(assignee_id=assignee)
        if s := params.get("status"):
            qs = qs.filter(status=s)
        return qs

    def perform_create(self, serializer):
        epic = serializer.validated_data["epic"]
        self.require_role(epic.organization_id, Role.MEMBER)
        story = serializer.save(
            created_by=self.request.user, number=_next_number(epic.stories.all())
        )
        story.snapshot(author=self.request.user, message="created")

    def perform_update(self, serializer):
        story = serializer.save()
        story.snapshot(author=self.request.user, message="updated")

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        story = self.get_object()
        ser = StoryTransitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            story.transition_to(ser.validated_data["to"])
        except InvalidTransition as exc:
            return Response(
                {"detail": str(exc), "code": "invalid_transition"},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(StorySerializer(story).data)

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        return self._paginated(self.get_object().versions.all(), VersionSerializer)


# --- helpers ---

def _unzip(blob: bytes) -> dict:
    """Decode a zip archive into a ``{path: text}`` mapping (text files only)."""
    files = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            files[info.filename] = zf.read(info.filename).decode("utf-8", "replace")
    return files


def _next_number(queryset) -> int:
    from django.db.models import Max

    return (queryset.aggregate(m=Max("number"))["m"] or 0) + 1


def _diff(a, b, field: str) -> str:
    def text(v):
        val = getattr(v, field)
        return val if isinstance(val, str) else json.dumps(val, indent=2, sort_keys=True)

    lines = difflib.unified_diff(
        text(a).splitlines(), text(b).splitlines(),
        fromfile=f"v{a.number}", tofile=f"v{b.number}", lineterm="",
    )
    return "\n".join(lines)
