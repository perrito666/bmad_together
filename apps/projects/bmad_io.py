"""BMAD ``docs/`` round-trip: import a file tree into the models and export it back.

The public surface is two pure functions over an in-memory ``{path: text}`` mapping,
so it is trivial to unit-test and reuse from the API (which wraps them in zip I/O):

    summary = import_tree(project, files, author=user)
    files   = export_tree(project)

Filename conventions follow BMAD (see docs/DATA_SCHEMAS.md import/export table).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

from apps.artifacts.models import Artifact, ArtifactType
from apps.projects.models import CoreConfig, Project, SprintStatus
from apps.workflow.models import Epic, Story, StoryStatus

# Canonical singleton documents: basename -> artifact type.
_SINGLETON_DOCS = {
    "brief.md": ArtifactType.BRIEF,
    "prd.md": ArtifactType.PRD,
    "architecture.md": ArtifactType.ARCHITECTURE,
    "front-end-spec.md": ArtifactType.UX_SPEC,
    "ux.md": ArtifactType.UX_SPEC,
    "ux-spec.md": ArtifactType.UX_SPEC,
    "research.md": ArtifactType.RESEARCH,
    "brainstorming.md": ArtifactType.BRAINSTORM,
}
_TYPE_TO_FILENAME = {
    ArtifactType.BRIEF: "docs/brief.md",
    ArtifactType.PRD: "docs/prd.md",
    ArtifactType.ARCHITECTURE: "docs/architecture.md",
    ArtifactType.UX_SPEC: "docs/front-end-spec.md",
    ArtifactType.RESEARCH: "docs/research.md",
    ArtifactType.BRAINSTORM: "docs/brainstorming.md",
}

_EPIC_FILE_RE = re.compile(r"epic-(\d+)\.md$", re.IGNORECASE)
_STORY_FILE_RE = re.compile(r"(\d+)\.(\d+)\.story\.md$", re.IGNORECASE)
_EPIC_HEADING_RE = re.compile(
    r"^##\s+Epic\s+(\d+)\s*[:.-]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^##\s*Status\s*\n+\s*([^\n]+)", re.IGNORECASE | re.MULTILINE)

_STATUS_WORDS = {
    "draft": StoryStatus.DRAFT,
    "approved": StoryStatus.APPROVED,
    "in progress": StoryStatus.IN_PROGRESS,
    "inprogress": StoryStatus.IN_PROGRESS,
    "in_progress": StoryStatus.IN_PROGRESS,
    "review": StoryStatus.REVIEW,
    "done": StoryStatus.DONE,
    "blocked": StoryStatus.BLOCKED,
}


@dataclass
class ImportSummary:
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    def bump(self, kind: str, *, created: bool):
        bucket = self.created if created else self.updated
        bucket[kind] = bucket.get(kind, 0) + 1

    def as_dict(self) -> dict:
        return {"created": self.created, "updated": self.updated, "skipped": self.skipped}


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


_TITLE_PREFIX_RE = re.compile(
    r"^(?:Story|Epic)\s+\d+(?:\.\d+)?\s*[:.\-]\s*", re.IGNORECASE
)


def _first_h1(text: str, default: str) -> str:
    m = _H1_RE.search(text or "")
    if not m:
        return default
    return _TITLE_PREFIX_RE.sub("", m.group(1).strip()).strip()


def _parse_status(text: str) -> str:
    m = _STATUS_RE.search(text or "")
    if not m:
        return StoryStatus.DRAFT
    word = m.group(1).strip().lower()
    return _STATUS_WORDS.get(word, StoryStatus.DRAFT)


# --- import ---

def import_tree(project: Project, files: dict[str, str], *, author=None) -> ImportSummary:
    """Upsert artifacts/epics/stories/config from a ``{path: text}`` mapping."""
    summary = ImportSummary()

    for path, content in files.items():
        base = _basename(path)
        text = content if isinstance(content, str) else content.decode("utf-8", "replace")

        if base == "core-config.yaml":
            _import_yaml_config(project, text, CoreConfig, summary, "core_config")
        elif base == "sprint-status.yaml":
            _import_yaml_config(project, text, SprintStatus, summary, "sprint_status")
        elif _STORY_FILE_RE.search(base):
            _import_story(project, base, text, author, summary)
        elif _EPIC_FILE_RE.search(base):
            _import_epic_file(project, base, text, author, summary)
        elif base in _SINGLETON_DOCS:
            _import_singleton(project, _SINGLETON_DOCS[base], base, text, author, summary)
            if _SINGLETON_DOCS[base] == ArtifactType.PRD:
                _import_epics_from_prd(project, text, author, summary)
        else:
            summary.skipped.append(path)

    return summary


def _import_yaml_config(project, text, model, summary, kind):
    data = yaml.safe_load(text) or {}
    obj, created = model.objects.get_or_create(project=project)
    obj.data = data
    obj.save(update_fields=["data"])
    summary.bump(kind, created=created)


def _import_singleton(project, art_type, base, text, author, summary):
    slug = base.rsplit(".", 1)[0]
    obj, created = Artifact.objects.update_or_create(
        project=project, type=art_type, slug=slug,
        defaults={"title": _first_h1(text, art_type.label), "body": text},
    )
    if not obj.created_by_id and author:
        obj.created_by = author
        obj.save(update_fields=["created_by"])
    obj.snapshot(author=author, message="imported")
    summary.bump(art_type, created=created)


def _upsert_epic(project, number, title, author, summary, *, body="", goal=""):
    epic, created = Epic.objects.update_or_create(
        project=project, number=number,
        defaults={"title": title, "body": body, "goal": goal},
    )
    if created and author:
        epic.created_by = author
        epic.save(update_fields=["created_by"])
    summary.bump("epic", created=created)
    return epic


def _import_epic_file(project, base, text, author, summary):
    number = int(_EPIC_FILE_RE.search(base).group(1))
    _upsert_epic(project, number, _first_h1(text, f"Epic {number}"), author, summary, body=text)


def _import_epics_from_prd(project, text, author, summary):
    for m in _EPIC_HEADING_RE.finditer(text):
        _upsert_epic(project, int(m.group(1)), m.group(2).strip(), author, summary)


def _import_story(project, base, text, author, summary):
    epic_num, story_num = (int(x) for x in _STORY_FILE_RE.search(base).groups())
    epic = _upsert_epic(project, epic_num, f"Epic {epic_num}", author, summary)
    story, created = Story.objects.update_or_create(
        epic=epic, number=story_num,
        defaults={
            "title": _first_h1(text, f"Story {epic_num}.{story_num}"),
            "body": text,
            "status": _parse_status(text),
        },
    )
    if created and author:
        story.created_by = author
        story.save(update_fields=["created_by"])
    story.snapshot(author=author, message="imported")
    summary.bump("story", created=created)


# --- export ---

def export_tree(project: Project) -> dict[str, str]:
    """Regenerate the canonical BMAD ``docs/`` tree as a ``{path: text}`` mapping."""
    files: dict[str, str] = {}

    config = CoreConfig.objects.filter(project=project).first()
    if config:
        files["core-config.yaml"] = yaml.safe_dump(config.data, sort_keys=False)
    sprint = SprintStatus.objects.filter(project=project).first()
    if sprint and sprint.data:
        files["sprint-status.yaml"] = yaml.safe_dump(sprint.data, sort_keys=False)

    for artifact in project.artifacts.all():
        if artifact.type in _TYPE_TO_FILENAME:
            files[_TYPE_TO_FILENAME[artifact.type]] = artifact.body or f"# {artifact.title}\n"
        elif artifact.type == ArtifactType.QA_GATE and artifact.target_story_id:
            label = artifact.target_story.label
            files[f"docs/qa/gates/{label}.md"] = artifact.body or f"# QA Gate {label}\n"

    for epic in project.epics.all():
        files[f"docs/prd/epic-{epic.number}.md"] = epic.body or _render_epic(epic)
        for story in epic.stories.all():
            files[f"docs/stories/{story.label}.story.md"] = story.body or _render_story(story)

    return files


def _render_epic(epic: Epic) -> str:
    return f"# Epic {epic.number}: {epic.title}\n\n{epic.goal}\n"


def _render_story(story: Story) -> str:
    out = [f"# Story {story.label}: {story.title}", "", "## Status", "", story.status, ""]
    if story.acceptance_criteria:
        out += ["## Acceptance Criteria", ""]
        out += [f"- {ac.get('text', ac) if isinstance(ac, dict) else ac}"
                for ac in story.acceptance_criteria]
        out.append("")
    return "\n".join(out)
