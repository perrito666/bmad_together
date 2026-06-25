import pytest

from apps.artifacts.factories import ArtifactFactory
from apps.artifacts.models import Artifact
from apps.core.models import Version
from apps.projects.models import CoreConfig, Project
from apps.workflow.factories import EpicFactory, StoryFactory
from apps.workflow.models import InvalidTransition, StoryStatus

pytestmark = pytest.mark.django_db


# --- versioning ---

def test_artifact_snapshot_increments_and_sets_current():
    art = ArtifactFactory(body="v1 body", data={"goals": ["a"]})
    v1 = art.snapshot(message="first")
    assert v1.number == 1
    assert art.current_version_id == v1.id

    art.body = "v2 body"
    art.save()
    v2 = art.snapshot(message="second")
    assert v2.number == 2
    assert v2.body == "v2 body"
    art.refresh_from_db()
    assert art.current_version_id == v2.id
    assert art.versions.count() == 2


def test_versions_are_per_object():
    a1 = ArtifactFactory()
    a2 = ArtifactFactory()
    a1.snapshot()
    a1.snapshot()
    a2.snapshot()
    assert a1.versions.count() == 2
    assert a2.versions.count() == 1
    assert Version.objects.count() == 3


def test_story_snapshots_share_version_table():
    story = StoryFactory(body="story body")
    v = story.snapshot(message="draft")
    assert v.number == 1
    assert story.current_version_id == v.id


# --- story state machine ---

def test_story_default_status_draft():
    assert StoryFactory().status == StoryStatus.DRAFT


def test_valid_transition_path():
    story = StoryFactory()
    story.transition_to(StoryStatus.APPROVED)
    story.transition_to(StoryStatus.IN_PROGRESS)
    story.transition_to(StoryStatus.REVIEW)
    story.refresh_from_db()
    assert story.status == StoryStatus.REVIEW


def test_invalid_transition_rejected():
    story = StoryFactory()  # draft
    with pytest.raises(InvalidTransition):
        story.transition_to(StoryStatus.DONE)


def test_done_requires_all_tasks_complete():
    story = StoryFactory(
        status=StoryStatus.REVIEW,
        tasks=[{"id": "T1", "text": "do", "done": False}],
    )
    with pytest.raises(InvalidTransition):
        story.transition_to(StoryStatus.DONE)

    story.tasks = [{"id": "T1", "text": "do", "done": True}]
    story.save()
    story.transition_to(StoryStatus.DONE)
    assert story.status == StoryStatus.DONE


def test_done_is_terminal():
    story = StoryFactory(status=StoryStatus.DONE)
    assert story.can_transition_to(StoryStatus.IN_PROGRESS) is False


def test_story_label():
    epic = EpicFactory(number=2)
    story = StoryFactory(epic=epic, number=3)
    assert story.label == "2.3"


# --- relationships & scoping helpers ---

def test_org_id_helpers_resolve_through_graph():
    epic = EpicFactory()
    story = StoryFactory(epic=epic)
    art = ArtifactFactory(project=epic.project)
    org_id = epic.project.organization_id
    assert epic.organization_id == org_id
    assert story.organization_id == org_id
    assert art.organization_id == org_id


def test_qa_gate_targets_story():
    story = StoryFactory()
    gate = ArtifactFactory(
        project=story.epic.project, type="qa_gate", target_story=story,
        data={"gate_decision": "PASS"},
    )
    assert gate in story.qa_gates.all()


def test_default_core_config_shape():
    project = EpicFactory().project
    cfg = CoreConfig.objects.create(project=project)
    assert cfg.data["prd"]["file"] == "docs/prd.md"
    assert cfg.organization_id == project.organization_id


def test_unique_story_number_per_epic():
    from django.db import IntegrityError

    epic = EpicFactory()
    StoryFactory(epic=epic, number=1)
    with pytest.raises(IntegrityError):
        StoryFactory(epic=epic, number=1)


def test_project_slug_autofill():
    from apps.accounts.factories import OrganizationFactory

    p = Project.objects.create(organization=OrganizationFactory(), name="My Cool App")
    assert p.slug == "my-cool-app"


def test_artifact_slug_autofill():
    art = Artifact.objects.create(
        project=EpicFactory().project, type="brief", title="The Brief"
    )
    assert art.slug == "the-brief"
