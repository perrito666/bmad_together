import pytest
from rest_framework.test import APIClient

from apps.accounts.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.accounts.models import Membership, Role
from apps.artifacts.factories import ArtifactFactory
from apps.projects.factories import ProjectFactory
from apps.workflow.factories import EpicFactory, StoryFactory
from apps.workflow.models import StoryStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def member_in(org, role=Role.MEMBER):
    m = MembershipFactory(organization=org, role=role)
    return m.user


# --- projects ---

def test_create_project_requires_membership(client):
    org = OrganizationFactory()
    outsider = UserFactory()
    client.force_authenticate(outsider)
    resp = client.post(
        "/api/v1/projects/", {"organization": str(org.id), "name": "App"}, format="json"
    )
    assert resp.status_code == 403


def test_create_project_sets_owner_and_config(client):
    org = OrganizationFactory()
    user = member_in(org)
    client.force_authenticate(user)
    resp = client.post(
        "/api/v1/projects/", {"organization": str(org.id), "name": "Cool App"}, format="json"
    )
    assert resp.status_code == 201
    assert str(resp.data["owner"]) == str(user.id)
    assert resp.data["slug"] == "cool-app"
    # config endpoint works and has BMAD defaults
    cfg = client.get(f"/api/v1/projects/{resp.data['id']}/config/")
    assert cfg.data["data"]["prd"]["file"] == "docs/prd.md"


def test_projects_scoped_to_membership(client):
    mine = ProjectFactory()
    member_user = MembershipFactory(organization=mine.organization).user
    ProjectFactory()  # someone else's
    client.force_authenticate(member_user)
    resp = client.get("/api/v1/projects/")
    ids = {r["id"] for r in resp.data["results"]}
    assert ids == {str(mine.id)}


def test_detail_of_foreign_project_is_404(client):
    other = ProjectFactory()
    client.force_authenticate(UserFactory())
    assert client.get(f"/api/v1/projects/{other.id}/").status_code == 404


# --- artifacts + versioning ---

def test_create_artifact_snapshots(client):
    project = ProjectFactory()
    user = member_in(project.organization)
    client.force_authenticate(user)
    resp = client.post(
        f"/api/v1/projects/{project.id}/artifacts/",
        {"type": "prd", "title": "PRD", "body": "## Goals", "data": {"goals": ["x"]}},
        format="json",
    )
    assert resp.status_code == 201
    aid = resp.data["id"]
    versions = client.get(f"/api/v1/artifacts/{aid}/versions/")
    assert len(versions.data["results"]) == 1
    assert versions.data["results"][0]["number"] == 1


def test_update_artifact_adds_version_and_diff(client):
    artifact = ArtifactFactory(body="line one")
    artifact.snapshot(message="created")
    user = member_in(artifact.project.organization)
    client.force_authenticate(user)

    resp = client.patch(
        f"/api/v1/artifacts/{artifact.id}/", {"body": "line two"}, format="json"
    )
    assert resp.status_code == 200
    diff = client.get(f"/api/v1/artifacts/{artifact.id}/diff/?from=1&to=2")
    assert "-line one" in diff.data["body"]
    assert "+line two" in diff.data["body"]


def test_viewer_cannot_write_artifact(client):
    artifact = ArtifactFactory()
    viewer = MembershipFactory(organization=artifact.project.organization, role=Role.VIEWER).user
    client.force_authenticate(viewer)
    resp = client.patch(
        f"/api/v1/artifacts/{artifact.id}/", {"title": "nope"}, format="json"
    )
    assert resp.status_code == 403


# --- epics + stories ---

def test_create_epic_autonumbers(client):
    project = ProjectFactory()
    user = member_in(project.organization)
    client.force_authenticate(user)
    e1 = client.post(f"/api/v1/projects/{project.id}/epics/", {"title": "E1"}, format="json")
    e2 = client.post(f"/api/v1/projects/{project.id}/epics/", {"title": "E2"}, format="json")
    assert e1.data["number"] == 1
    assert e2.data["number"] == 2


def test_create_story_under_epic_autonumbers_and_labels(client):
    epic = EpicFactory(number=2)
    user = member_in(epic.project.organization)
    client.force_authenticate(user)
    resp = client.post(
        f"/api/v1/epics/{epic.id}/stories/", {"title": "Login"}, format="json"
    )
    assert resp.status_code == 201
    assert resp.data["number"] == 1
    assert resp.data["label"] == "2.1"


def test_story_transition_valid_and_invalid(client):
    story = StoryFactory()
    user = member_in(story.epic.project.organization)
    client.force_authenticate(user)
    url = f"/api/v1/stories/{story.id}/transition/"

    ok = client.post(url, {"to": "approved"}, format="json")
    assert ok.status_code == 200 and ok.data["status"] == "approved"

    bad = client.post(url, {"to": "done"}, format="json")
    assert bad.status_code == 409
    assert bad.data["code"] == "invalid_transition"


def test_story_done_requires_tasks(client):
    story = StoryFactory(
        status=StoryStatus.REVIEW, tasks=[{"id": "T1", "text": "x", "done": False}]
    )
    user = member_in(story.epic.project.organization)
    client.force_authenticate(user)
    url = f"/api/v1/stories/{story.id}/transition/"
    assert client.post(url, {"to": "done"}, format="json").status_code == 409


def test_next_story_returns_first_non_done(client):
    epic = EpicFactory(number=1)
    user = member_in(epic.project.organization)
    s1 = StoryFactory(epic=epic, number=1, status=StoryStatus.DONE)  # noqa: F841
    s2 = StoryFactory(epic=epic, number=2, status=StoryStatus.APPROVED)
    client.force_authenticate(user)
    resp = client.post(f"/api/v1/projects/{epic.project.id}/next-story/")
    assert resp.status_code == 200
    assert resp.data["id"] == str(s2.id)


def test_stories_filter_by_status(client):
    epic = EpicFactory()
    user = member_in(epic.project.organization)
    StoryFactory(epic=epic, number=1, status=StoryStatus.DRAFT)
    StoryFactory(epic=epic, number=2, status=StoryStatus.APPROVED)
    client.force_authenticate(user)
    resp = client.get(f"/api/v1/stories/?epic={epic.id}&status=approved")
    assert len(resp.data["results"]) == 1


def test_unauthenticated_rejected(client):
    assert client.get("/api/v1/projects/").status_code == 401


def test_member_count_role_helper():
    # sanity: an org admin counts as member+ for writes
    org = OrganizationFactory()
    admin = MembershipFactory(organization=org, role=Role.ADMIN).user
    assert Membership.objects.filter(user=admin, organization=org).exists()
