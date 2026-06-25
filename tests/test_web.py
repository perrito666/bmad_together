import pytest
from django.test import Client

from apps.accounts.factories import MembershipFactory, UserFactory
from apps.accounts.models import Role
from apps.artifacts.factories import ArtifactFactory
from apps.projects.factories import ProjectFactory
from apps.workflow.factories import EpicFactory, StoryFactory
from apps.workflow.models import StoryStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def login_member(client, org, role=Role.MEMBER):
    user = MembershipFactory(organization=org, role=role).user
    client.force_login(user)
    return user


def test_dashboard_requires_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url


def test_dashboard_lists_active_org_projects(client):
    project = ProjectFactory()
    login_member(client, project.organization)
    resp = client.get("/")
    assert resp.status_code == 200
    assert project.name.encode() in resp.content


def test_project_detail_shows_artifacts(client):
    artifact = ArtifactFactory(title="My PRD")
    login_member(client, artifact.project.organization)
    resp = client.get(f"/projects/{artifact.project.id}/")
    assert resp.status_code == 200
    assert b"My PRD" in resp.content


def test_foreign_project_404(client):
    other = ProjectFactory()
    user = UserFactory()
    client.force_login(user)
    assert client.get(f"/projects/{other.id}/").status_code == 404


def test_artifact_detail_renders_markdown(client):
    artifact = ArtifactFactory(body="# Hello\n\nworld")
    artifact.snapshot(message="created")
    login_member(client, artifact.project.organization)
    resp = client.get(f"/artifacts/{artifact.id}/")
    assert resp.status_code == 200
    assert b"<h1>Hello</h1>" in resp.content


def test_artifact_edit_creates_version(client):
    artifact = ArtifactFactory(body="v1")
    artifact.snapshot(message="created")
    login_member(client, artifact.project.organization)
    resp = client.post(
        f"/artifacts/{artifact.id}/edit/",
        {"title": artifact.title, "status": "approved", "body": "v2", "message": "edit"},
    )
    assert resp.status_code == 302
    artifact.refresh_from_db()
    assert artifact.body == "v2"
    assert artifact.versions.count() == 2


def test_viewer_cannot_open_edit(client):
    artifact = ArtifactFactory()
    login_member(client, artifact.project.organization, role=Role.VIEWER)
    assert client.get(f"/artifacts/{artifact.id}/edit/").status_code == 403


def test_board_renders_columns(client):
    epic = EpicFactory()
    StoryFactory(epic=epic, number=1, status=StoryStatus.DRAFT, title="Draft story")
    login_member(client, epic.project.organization)
    resp = client.get(f"/projects/{epic.project.id}/board/")
    assert resp.status_code == 200
    assert b"Draft story" in resp.content
    assert b"In Progress" in resp.content


def test_htmx_transition_swaps_board(client):
    story = StoryFactory(status=StoryStatus.DRAFT)
    login_member(client, story.epic.project.organization)
    resp = client.post(
        f"/stories/{story.id}/transition/",
        {"to": "approved"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    story.refresh_from_db()
    assert story.status == StoryStatus.APPROVED
    assert b"board" in resp.content or b"col" in resp.content


def test_non_htmx_transition_redirects(client):
    story = StoryFactory(status=StoryStatus.DRAFT)
    login_member(client, story.epic.project.organization)
    resp = client.post(f"/stories/{story.id}/transition/", {"to": "approved"})
    assert resp.status_code == 302


def test_diff_partial(client):
    artifact = ArtifactFactory(body="alpha")
    artifact.snapshot(message="v1")
    artifact.body = "beta"
    artifact.save()
    artifact.snapshot(message="v2")
    login_member(client, artifact.project.organization)
    resp = client.get(f"/artifacts/{artifact.id}/diff/?from=1&to=2")
    assert resp.status_code == 200
    assert b"-alpha" in resp.content and b"+beta" in resp.content


def test_org_switcher_sets_session(client):
    p1 = ProjectFactory()
    user = MembershipFactory(organization=p1.organization).user
    # second org for the same user
    p2 = ProjectFactory()
    MembershipFactory(user=user, organization=p2.organization)
    client.force_login(user)
    client.post("/set-org/", {"org": str(p2.organization.id)})
    resp = client.get("/")
    assert p2.name.encode() in resp.content
