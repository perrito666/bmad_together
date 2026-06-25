"""HTMX-driven web UI for browsing and editing BMAD artifacts."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ROLE_RANK, Organization, Role
from apps.accounts.scoping import accessible_org_ids, user_role_in_org
from apps.artifacts.models import Artifact, ArtifactType
from apps.projects.models import Project
from apps.workflow.models import (
    STORY_TRANSITIONS,
    InvalidTransition,
    Story,
    StoryStatus,
)

BOARD_COLUMNS = [
    StoryStatus.DRAFT,
    StoryStatus.APPROVED,
    StoryStatus.IN_PROGRESS,
    StoryStatus.REVIEW,
    StoryStatus.DONE,
    StoryStatus.BLOCKED,
]


# --- scoping helpers ---

def _org_ids(request):
    return accessible_org_ids(request.user)


def active_org(request):
    """The org the user is currently viewing (session-sticky, default first)."""
    orgs = Organization.objects.filter(id__in=_org_ids(request)).order_by("name")
    active_id = request.session.get("active_org_id")
    org = orgs.filter(id=active_id).first() if active_id else None
    return org or orgs.first()


def _can_write(request, org_id) -> bool:
    role = user_role_in_org(request.user, org_id)
    return role is not None and ROLE_RANK[role] >= ROLE_RANK[Role.MEMBER]


def _projects(request):
    return Project.objects.filter(organization_id__in=_org_ids(request))


def _artifacts(request):
    return Artifact.objects.filter(project__organization_id__in=_org_ids(request))


def _stories(request):
    return Story.objects.filter(epic__project__organization_id__in=_org_ids(request))


def _nav(request, **extra):
    org = extra.pop("org", None) or active_org(request)
    ctx = {
        "active_org": org,
        "all_orgs": Organization.objects.filter(id__in=_org_ids(request)).order_by("name"),
    }
    ctx.update(extra)
    return ctx


# --- views ---

@login_required
def dashboard(request):
    org = active_org(request)
    projects = _projects(request).filter(organization=org) if org else _projects(request).none()
    projects = projects.annotate(n_artifacts=Count("artifacts", distinct=True),
                                 n_epics=Count("epics", distinct=True))
    return render(request, "web/dashboard.html", _nav(request, org=org, projects=projects))


@login_required
@require_POST
def set_org(request):
    org_id = request.POST.get("org")
    if org_id and str(org_id) in {str(i) for i in _org_ids(request)}:
        request.session["active_org_id"] = str(org_id)
    return redirect("web:dashboard")


@login_required
def project_detail(request, pk):
    project = get_object_or_404(_projects(request), pk=pk)
    artifacts_by_type = {}
    for t in ArtifactType.values:
        items = project.artifacts.filter(type=t)
        if items.exists():
            artifacts_by_type[t] = items
    epics = project.epics.annotate(n=Count("stories")).order_by("number")
    ctx = _nav(
        request, org=project.organization, project=project,
        artifacts_by_type=artifacts_by_type, epics=epics,
        can_write=_can_write(request, project.organization_id),
    )
    return render(request, "web/project_detail.html", ctx)


@login_required
def artifact_detail(request, pk):
    artifact = get_object_or_404(_artifacts(request), pk=pk)
    ctx = _nav(
        request, org=artifact.project.organization, artifact=artifact,
        versions=artifact.versions.all(),
        can_write=_can_write(request, artifact.organization_id),
    )
    return render(request, "web/artifact_detail.html", ctx)


@login_required
def artifact_edit(request, pk):
    artifact = get_object_or_404(_artifacts(request), pk=pk)
    if not _can_write(request, artifact.organization_id):
        return HttpResponseForbidden("You need write access for this organization.")
    if request.method == "POST":
        artifact.title = request.POST.get("title", artifact.title)
        artifact.status = request.POST.get("status", artifact.status)
        artifact.body = request.POST.get("body", artifact.body)
        artifact.save()
        artifact.snapshot(author=request.user, message=request.POST.get("message", "edited"))
        messages.success(request, "Artifact saved (new version created).")
        return redirect("web:artifact_detail", pk=artifact.pk)
    ctx = _nav(
        request, org=artifact.project.organization, artifact=artifact,
        statuses=Artifact._meta.get_field("status").choices,
    )
    return render(request, "web/artifact_form.html", ctx)


@login_required
def artifact_diff(request, pk):
    artifact = get_object_or_404(_artifacts(request), pk=pk)
    versions = list(artifact.versions.all())
    try:
        a = artifact.versions.get(number=request.GET.get("from"))
        b = artifact.versions.get(number=request.GET.get("to"))
        from apps.api.domain_views import _diff
        body_diff = _diff(a, b, "body")
        data_diff = _diff(a, b, "data")
    except Exception:  # noqa: BLE001 - any bad/missing version -> empty diff
        body_diff = data_diff = ""
    ctx = {
        "artifact": artifact, "versions": versions,
        "body_diff": body_diff, "data_diff": data_diff,
        "from": request.GET.get("from"), "to": request.GET.get("to"),
    }
    return render(request, "web/partials/diff.html", ctx)


@login_required
def board(request, pk):
    project = get_object_or_404(_projects(request), pk=pk)
    ctx = _board_context(request, project)
    return render(request, "web/board.html", ctx)


def _board_context(request, project):
    stories = (
        Story.objects.filter(epic__project=project)
        .select_related("epic", "assignee")
        .order_by("epic__number", "number")
    )
    columns = [
        {"status": s, "label": s.replace("_", " ").title(),
         "stories": [st for st in stories if st.status == s]}
        for s in BOARD_COLUMNS
    ]
    return _nav(
        request, org=project.organization, project=project, columns=columns,
        can_write=_can_write(request, project.organization_id),
    )


@login_required
@require_POST
def story_transition(request, pk):
    story = get_object_or_404(_stories(request), pk=pk)
    if not _can_write(request, story.organization_id):
        return HttpResponseForbidden("You need write access for this organization.")
    target = request.POST.get("to")
    try:
        story.transition_to(target)
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    # From the board (HTMX): swap the columns. From story detail: redirect back.
    if request.headers.get("HX-Request"):
        ctx = _board_context(request, story.epic.project)
        return render(request, "web/partials/board_columns.html", ctx)
    return redirect("web:story_detail", pk=story.pk)


@login_required
def story_detail(request, pk):
    story = get_object_or_404(_stories(request), pk=pk)
    ctx = _nav(
        request, org=story.epic.project.organization, story=story,
        allowed_targets=sorted(STORY_TRANSITIONS.get(story.status, set())),
        can_write=_can_write(request, story.organization_id),
    )
    return render(request, "web/story_detail.html", ctx)
