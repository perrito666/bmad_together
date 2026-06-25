import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role
from apps.projects.models import Project
from apps.workflow.factories import EpicFactory, StoryFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def _member(org):
    return MembershipFactory(organization=org, role=Role.MEMBER).user


def test_story_search_by_q(client):
    epic = EpicFactory()
    StoryFactory(epic=epic, number=1, title="Login flow")
    StoryFactory(epic=epic, number=2, title="Logout button")
    client.force_authenticate(_member(epic.project.organization))
    resp = client.get(f"/api/v1/stories/?project={epic.project.id}&q=login")
    titles = [r["title"] for r in resp.data["results"]]
    assert titles == ["Login flow"]


def test_epic_search_by_q(client):
    project = EpicFactory(number=1, title="Payments").project
    EpicFactory(project=project, number=2, title="Onboarding")
    client.force_authenticate(_member(project.organization))
    resp = client.get(f"/api/v1/epics/?project={project.id}&q=payments")
    assert len(resp.data["results"]) == 1


def test_seed_demo_is_idempotent():
    call_command("seed_demo", "--email", "d@example.com")
    call_command("seed_demo", "--email", "d@example.com")
    assert Project.objects.filter(slug="demo-app").count() == 1
    project = Project.objects.get(slug="demo-app")
    assert project.epics.count() == 2
    assert project.epics.get(number=1).stories.count() == 2


def test_openapi_schema_endpoint(client):
    user = _member(EpicFactory().project.organization)
    client.force_authenticate(user)
    resp = client.get("/api/schema/")
    assert resp.status_code == 200


def test_healthz_public(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
