import io
import zipfile

import pytest
from rest_framework.test import APIClient

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role
from apps.artifacts.models import Artifact, ArtifactType
from apps.projects.bmad_io import export_tree, import_tree
from apps.projects.factories import ProjectFactory
from apps.workflow.factories import StoryFactory
from apps.workflow.models import Epic, Story, StoryStatus

pytestmark = pytest.mark.django_db


SAMPLE = {
    "core-config.yaml": "prd:\n  file: docs/prd.md\n  sharded: true\n",
    "sprint-status.yaml": "epics:\n  - number: 1\n    status: active\n",
    "docs/brief.md": "# Project Brief\n\nWe build things.",
    "docs/prd.md": (
        "# PRD\n\n## Epic 1: Foundations\n\nGoal text.\n\n## Epic 2: Payments\n\nMore.\n"
    ),
    "docs/architecture.md": "# Architecture\n\nMonolith.",
    "docs/stories/1.1.story.md": (
        "# Story 1.1: Login\n\n## Status\n\nApproved\n\n## Acceptance Criteria\n\n- works"
    ),
}


def test_import_tree_creates_objects():
    project = ProjectFactory()
    summary = import_tree(project, SAMPLE)

    assert project.config.data["prd"]["file"] == "docs/prd.md"
    assert project.sprint_status.data["epics"][0]["number"] == 1
    assert Artifact.objects.filter(project=project, type=ArtifactType.BRIEF).exists()
    assert Artifact.objects.filter(project=project, type=ArtifactType.PRD).exists()

    # Epics 1 & 2 parsed from the PRD headings; story 1.1 created under epic 1.
    assert Epic.objects.filter(project=project, number=1).exists()
    assert Epic.objects.filter(project=project, number=2).exists()
    story = Story.objects.get(epic__project=project, epic__number=1, number=1)
    assert story.title == "Login"
    assert story.status == StoryStatus.APPROVED
    assert summary.created["story"] == 1


def test_import_is_idempotent_upsert():
    project = ProjectFactory()
    import_tree(project, SAMPLE)
    import_tree(project, SAMPLE)
    # No duplicates on second import.
    assert Artifact.objects.filter(project=project, type=ArtifactType.BRIEF).count() == 1
    assert Epic.objects.filter(project=project).count() == 2
    assert Story.objects.filter(epic__project=project).count() == 1


def test_export_after_import_roundtrips_key_files():
    project = ProjectFactory()
    import_tree(project, SAMPLE)
    out = export_tree(project)
    assert "core-config.yaml" in out
    assert "docs/brief.md" in out
    assert "docs/prd/epic-1.md" in out
    assert "docs/stories/1.1.story.md" in out
    assert "Login" in out["docs/stories/1.1.story.md"]


def test_export_renders_story_without_body():
    story = StoryFactory(number=1, title="Generated", status=StoryStatus.DRAFT, body="")
    out = export_tree(story.epic.project)
    rendered = out[f"docs/stories/{story.label}.story.md"]
    assert "Generated" in rendered
    assert "## Status" in rendered


# --- API endpoints ---

@pytest.fixture
def client():
    return APIClient()


def _member(project):
    return MembershipFactory(organization=project.organization, role=Role.MEMBER).user


def test_import_endpoint_json(client):
    project = ProjectFactory()
    client.force_authenticate(_member(project))
    resp = client.post(
        f"/api/v1/projects/{project.id}/import/", {"files": SAMPLE}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["created"]["brief"] == 1


def test_import_endpoint_zip(client):
    project = ProjectFactory()
    client.force_authenticate(_member(project))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in SAMPLE.items():
            zf.writestr(path, content)
    buf.seek(0)
    buf.name = "docs.zip"
    resp = client.post(
        f"/api/v1/projects/{project.id}/import/", {"file": buf}, format="multipart"
    )
    assert resp.status_code == 200
    assert Epic.objects.filter(project=project).count() == 2


def test_export_endpoint_returns_zip(client):
    project = ProjectFactory()
    import_tree(project, SAMPLE)
    client.force_authenticate(_member(project))
    resp = client.get(f"/api/v1/projects/{project.id}/export/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
    assert "docs/brief.md" in names
    assert "docs/stories/1.1.story.md" in names


def test_export_endpoint_json(client):
    project = ProjectFactory()
    import_tree(project, SAMPLE)
    client.force_authenticate(_member(project))
    resp = client.get(f"/api/v1/projects/{project.id}/export/?format=json")
    assert resp.status_code == 200
    assert "core-config.yaml" in resp.data["files"]


def test_import_requires_member(client):
    project = ProjectFactory()
    viewer = MembershipFactory(organization=project.organization, role=Role.VIEWER).user
    client.force_authenticate(viewer)
    resp = client.post(
        f"/api/v1/projects/{project.id}/import/", {"files": SAMPLE}, format="json"
    )
    assert resp.status_code == 403
