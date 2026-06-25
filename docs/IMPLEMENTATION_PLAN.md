# bmad_together — Implementation Plan

A Django platform that turns [BMAD](https://github.com/bmad-code-org/BMAD-METHOD)
artifacts into first-class, multi-tenant database records with a REST API and a
web UI — and lets coding tools (Claude Code, Codex, OpenCode, Amp) read and write
those artifacts through the platform instead of loose markdown files in `docs/`.

> Goal: make BMAD produce **meaningful, queryable, governed documentation after
> the fact**, scoped per user / team / organization.

---

## 1. Background: what BMAD produces

BMAD (Breakthrough Method for Agile AI-Driven Development) runs a project through
a pipeline of role-based AI agents, each producing versioned documents. Today
those documents are markdown files committed to a repo's `docs/` folder.

### Agents (roles)

| Agent | Persona | Produces / owns |
|-------|---------|-----------------|
| Analyst | Mary | Brainstorming output, market/competitor research, Project Brief |
| PM | John | PRD (functional + non-functional requirements, epics, draft stories) |
| UX Expert | Sally | UX / front-end spec |
| Architect | Winston | Architecture document (full-stack) |
| PO | Sarah | Backlog validation, sharding, document alignment |
| Scrum Master | Bob | Epics and hyper-detailed Stories |
| Dev | James | Implementation against a Story; updates dev notes / status |
| QA / Test Architect | Quinn | QA gates and assessments on Stories |
| BMad Master / Orchestrator | — | Cross-cutting orchestration |

### Artifacts

- **Brainstorming output**
- **Project Brief**
- **Market / Competitor Research**
- **PRD** — functional requirements (FRs), non-functional requirements (NFRs),
  **epics**, and draft **stories**
- **UX / Front-end Spec**
- **Architecture Document**
- **Epics** — `epic-{n}.md`
- **Stories** — `{epicNum}.{storyNum}.story.md`, with a status lifecycle, task
  checklist, dev notes, and QA results embedded
- **QA gates / assessments**
- **Tracking**: `sprint-status.yaml`, `core-config.yaml`

Everything is treated as a **versioned asset** — version history is a first-class
requirement, not an afterthought.

---

## 2. Goals & non-goals

### Goals
- Model every BMAD artifact as a Django model with structured fields + markdown body.
- Full version history per artifact (BMAD treats every doc as versioned).
- Multi-tenancy: every artifact is constrained to an **organization**, optionally
  a **team**, and an **owner**, with role-based access.
- REST API (read + write) covering all artifacts.
- Web UI (Django templates + HTMX) for creating and visualizing artifacts.
- Per-tool **plugins** (REST-based scripts) for Claude Code, Codex, OpenCode, and
  Amp so those tools use the platform as the system of record instead of local files.
- Round-trip import/export with the canonical BMAD `docs/` markdown layout.

### Non-goals (initial)
- Reimplementing the BMAD agents themselves. We store/serve artifacts; the agents
  still run inside the user's coding tool.
- Real-time collaborative editing (CRDT). Versioned saves are enough for v1.
- Billing / org provisioning beyond basic CRUD.

---

## 3. Architecture overview

Single Django 5 project, modular apps, PostgreSQL (JSONB for structured fields),
Django REST Framework for the API, Django templates + HTMX for the UI, and a
REST-based plugin generator for the coding tools.

```
bmad_together/
├── config/                 # settings (base/dev/prod), urls, asgi/wsgi
├── apps/
│   ├── accounts/           # User, Organization, Team, Membership, roles
│   ├── projects/           # Project (a BMAD workspace) + CoreConfig
│   ├── artifacts/          # Artifact, ArtifactVersion, types, attachments
│   ├── workflow/           # Epic, Story, status lifecycle, SprintStatus
│   ├── api/                # DRF routers, serializers, viewsets, permissions
│   └── web/                # HTMX views, templates, static
├── plugins/                # REST-based per-tool generators (claude/codex/opencode/amp)
│   ├── common/             # shared CLI client + auth handling
│   ├── claude/
│   ├── codex/
│   ├── opencode/
│   └── amp/
├── docs/                   # this plan, architecture, ADRs
├── tests/
├── compose.yaml            # Postgres + app for local dev
├── pyproject.toml          # deps, ruff, pytest config
└── manage.py
```

### Tech stack
- **Django 5**, **Django REST Framework**, **drf-spectacular** (OpenAPI).
- **django-allauth** (local email/password + Google/GitHub SSO).
- **djangorestframework-simplejwt** (interactive JWT) + a custom PAT model (CLI/automation).
- **PostgreSQL** (JSONB structured fields, full-text search later).
- **Django templates + HTMX** for the UI (+ a little Alpine.js for interactivity);
  `markdown` + bleach for safe rendering; `difflib`/diff rendering for versions.
- **pytest-django**, **factory_boy**, **Ruff**, **mypy** (optional), **pre-commit**.
- **Docker Compose** for local dev; gunicorn/uvicorn for prod.

---

## 4. Data model

Tenancy strategy: **shared database with row-level scoping** (not schema- or
DB-per-tenant). Simplest to operate and adequate at this scale; every tenant-owned
row carries `organization` (+ optional `team`, `owner`) and all querysets are
scoped through permission classes / managers.

### 4.1 accounts

```
User(AbstractUser)                      # custom user from day 1
Organization(name, slug, created_at)
Team(organization FK, name, slug)
Membership(user FK, organization FK, team FK?null, role)
    role ∈ {owner, admin, member, viewer}
Invitation(organization FK, team FK?null, email, role,
           invited_by FK, token, status, expires_at)
    status ∈ {pending, accepted, revoked, expired}
APIToken(user FK, name, prefix, hashed_key, scopes, last_used_at,
         created_at, revoked_at?)       # personal access tokens for the CLI
```

**Membership is invite-only.** There is no self-serve org creation in the app:
organizations are provisioned by platform staff (Django admin / a restricted
endpoint), and users join exclusively by accepting an `Invitation` (which creates
their `Membership`). An org `owner`/`admin` can invite others to their org/team.

Access rule: a user sees an artifact iff they share its `organization` (and, when
the artifact is team-scoped, its `team`), with write gated by role.

Authentication: **django-allauth** provides local email/password **and** Google /
GitHub SSO. SSO sign-in still only grants access to orgs the user was invited to.

### 4.2 projects

```
Project(organization FK, team FK?null, owner FK, name, slug, description, created_at)
    # one BMAD "workspace"; all artifacts belong to a project
CoreConfig(project O2O, data JSONB)     # mirrors core-config.yaml (paths, options)
```

### 4.3 artifacts (generic, versioned)

```
ArtifactType  ∈ {brief, research, prd, ux_spec, architecture,
                 epic, story, qa_gate, brainstorm, sprint_status, other}

Artifact(
    project FK, type, title, slug, status,
    body            TEXT,        # markdown
    data            JSONB,       # structured fields specific to the type
    created_by FK, created_at, updated_at,
    current_version FK?          # → ArtifactVersion
)

ArtifactVersion(                 # immutable snapshot, created on every save
    artifact FK, number,
    body TEXT, data JSONB,
    author FK, created_at, message
)

Attachment(artifact FK, file, uploaded_by, created_at)
```

`data` holds type-specific structure, e.g. a PRD stores `functional_requirements`,
`non_functional_requirements`, `epics[]`; research stores findings; etc. This keeps
one flexible table while still being queryable via JSONB.

### 4.4 workflow (first-class lifecycle objects)

Epics and Stories get dedicated models because they carry real state and relations.

```
Epic(project FK, number, title, goal, status, body, data JSONB,
     created_by, timestamps)

Story(
    epic FK, number,             # → {epic.number}.{number}
    title, status,
    acceptance_criteria JSONB,
    tasks JSONB,                 # checklist items with done flags
    dev_notes TEXT,
    qa_results JSONB,
    body TEXT, data JSONB,
    assignee FK?null, created_by, timestamps
)
    Story.status ∈ {draft, approved, in_progress, review, done, blocked}

SprintStatus(project O2O, data JSONB)    # mirrors sprint-status.yaml
```

Stories are also versioned (reuse the ArtifactVersion pattern or a parallel
`StoryVersion`). PRD → Epics → Stories → QA gates form a navigable graph via FKs.

### 4.5 Relationships

PRD links to its Epics; Epics link to Stories; Stories link to QA gates; the
Architecture/UX docs link to the Project. Surfaced in API as nested routes and in
the UI as breadcrumbs + a project graph view.

---

## 5. REST API (DRF)

Versioned under `/api/v1/`. **Three auth paths**: session (web UI, via allauth),
**JWT** (`simplejwt`) for interactive/programmatic API clients, and **personal
access tokens** (`APIToken`, custom DRF auth class) for the `bmadt` CLI and
unattended automation. **Object-level permissions** enforce org/team/owner scope on
every queryset (a base `TenantScopedViewSet` filters by the requester's memberships).

Endpoints (representative):

```
GET/POST   /api/v1/orgs/                          /orgs/{id}/
GET/POST   /api/v1/teams/
GET/POST   /api/v1/projects/                      /projects/{id}/
GET        /api/v1/projects/{id}/config/          (CoreConfig)
GET/POST   /api/v1/projects/{id}/artifacts/       ?type=&status=
GET/PUT    /api/v1/artifacts/{id}/
GET        /api/v1/artifacts/{id}/versions/       /versions/{n}/   (+ diff)
GET/POST   /api/v1/projects/{id}/epics/
GET/POST   /api/v1/epics/{id}/stories/
GET/PUT    /api/v1/stories/{id}/
POST       /api/v1/stories/{id}/transition/       {to: "in_progress"}
GET        /api/v1/projects/{id}/sprint-status/
POST       /api/v1/projects/{id}/import/          (BMAD docs/ markdown bundle)
GET        /api/v1/projects/{id}/export/          (BMAD docs/ markdown bundle)
```

- Filtering/search by type, status, epic, assignee.
- Story status transitions validated against the lifecycle.
- OpenAPI schema + Swagger UI via drf-spectacular (the plugins consume this).

---

## 6. Web UI (Django templates + HTMX)

- **Auth & org switcher**: login, pick active org/team.
- **Project dashboard**: artifacts grouped by type, recent activity, status rollup.
- **Artifact detail**: rendered markdown + structured fields; inline HTMX edit;
  version history with side-by-side diff.
- **Epic → Story board**: kanban columns by Story status, drag/HTMX transitions.
- **Story detail**: acceptance criteria, task checklist, dev notes, QA results.
- **Project graph**: PRD → Epics → Stories → QA navigation.
- **Markdown editor**: edit `body`, structured fields via forms; safe render
  (`markdown` + `bleach`).

HTMX keeps it server-rendered and fast to build; Alpine.js only where needed.

---

## 7. Plugin layer (REST-based, per tool)

**Decision: REST-only, per-tool scripts** (no MCP). Each plugin is generated into a
target repo and configures that tool's agents/commands to call the platform's REST
API instead of reading/writing local `docs/` files.

### Shared core (`plugins/common/`)
- A small CLI client (`bmadt`) that authenticates with a per-user API token and
  wraps the REST endpoints: `bmadt get story 1.2`, `bmadt set story 1.2 --status review`,
  `bmadt push prd`, `bmadt pull architecture`, `bmadt list stories --status approved`.
- Config: `.bmadt/config.toml` (base URL, project id, token via env var) per repo.
- Output formats: markdown (for the agent to read) and JSON (for scripting).

### Per-tool shims
Each generator writes the tool's native config so its BMAD agents invoke `bmadt`:

- **Claude Code** — `.claude/commands/*.md` slash commands and agent definitions
  that call `bmadt ...`; documented in `CLAUDE.md`.
- **Codex** — `AGENTS.md` instructions + command snippets that shell out to `bmadt`.
- **OpenCode** — `opencode.json` agent/command entries wired to `bmadt`.
- **Amp** — `AGENTS.md` + toolbox/command entries calling `bmadt`.

A generator command (`python -m plugins.install --tool claude --project <id>`)
lays down the right files per repo, mirroring how `npx bmad-method install` scaffolds
tool files — but pointed at bmad_together. This keeps tool-specific knowledge in one
place and reuses the single REST client.

### Auth for tools
The CLI authenticates with a **personal access token** (`APIToken`) issued from the
web UI — revocable, named, scoped to the user's orgs. The CLI reads it from an env
var (e.g. `BMADT_TOKEN`) so it never lands in the repo. (Interactive API clients can
alternatively use JWT, but PATs are the recommended path for unattended tools.)

---

## 8. Import / export & round-trip

To adopt incrementally, the platform reads and writes the canonical BMAD `docs/`
layout:

- **Import**: parse `docs/brief.md`, `docs/prd.md` (+ sharded `epic-*.md`),
  `docs/architecture.md`, `docs/stories/{e}.{s}.story.md`, `sprint-status.yaml`,
  `core-config.yaml` → create Artifacts/Epics/Stories.
- **Export**: regenerate that exact tree so a repo can fall back to file-based BMAD
  at any time (no lock-in).

This also defines the structured `data` schemas per artifact type (derived from the
BMAD templates).

---

## 9. Milestones

1. **Scaffold** — Django project, settings split, Docker/Postgres, custom User,
   Organization/Team/Membership + Invitation + APIToken, django-allauth (local +
   Google/GitHub SSO), invite-acceptance flow, admin. CI (ruff + pytest).
2. **Domain** — Project/CoreConfig, Artifact + ArtifactVersion, Epic/Story models,
   admin, factories, model tests.
3. **REST API** — `TenantScopedViewSet`, serializers, permissions, transitions,
   JWT + PAT auth classes, OpenAPI schema, API tests.
4. **Web UI** — dashboards, artifact CRUD + markdown render, version diff, story
   kanban.
5. **Import/Export** — BMAD `docs/` round-trip + structured `data` schemas.
6. **Plugin layer** — `bmadt` CLI client + generators for claude/codex/opencode/amp,
   API tokens, docs.
7. **Polish** — search, activity feed, seed data, deployment, hardening.

Each milestone is a reviewable PR. v1 = milestones 1–6.

---

## 10. Key decisions (made)

- **Plugin transport**: REST-only, per-tool generated scripts (no MCP).
- **Web UI**: Django templates + HTMX.
- **Tenancy**: shared DB with row-level org/team/owner scoping.
- **Versioning**: whole-document immutable `ArtifactVersion` snapshot on every save
  (no per-field diff tracking in v1).
- **Auth**: django-allauth — local email/password **plus** Google/GitHub SSO.
- **API tokens**: **both** — personal access tokens for the `bmadt` CLI/automation,
  JWT for interactive API clients.
- **Org model**: **invite-only** — no self-serve org creation; users join via
  `Invitation` acceptance.

## 11. Resolved edges (v1 defaults)

These were the leftover narrow questions; resolved with defaults below (override later
without reshaping the design):

- **Org provisioning** → platform staff create orgs via Django admin (or a restricted
  staff-only endpoint). No public "create org" in v1.
- **Invitation delivery** → signed, expiring **invite link** (token in URL) shown in the
  UI and emailable; pluggable email backend (console in dev, SMTP/provider in prod) so we
  don't hard-depend on a vendor for v1.
- **SSO domain capture** → off. SSO authenticates identity only; access still requires an
  explicit `Invitation`.
- **PAT scopes** → tokens are **user-wide read-write** in v1 (scoped to the user's
  memberships), with an optional `scopes` field reserved on `APIToken` for future
  per-project / read-only refinement.

## 12. Companion docs

- **[DATA_MODEL.md](DATA_MODEL.md)** — ER diagram of the full model graph and the
  tenant-scoping invariants.
- **[DATA_SCHEMAS.md](DATA_SCHEMAS.md)** — the JSONB `data` shape per artifact type,
  the Story status state machine, and the BMAD `docs/` import/export mapping.
- **[API.md](API.md)** — the REST contract: endpoints, serializer sketches,
  permissions, pagination, and the error model.
- **[PLUGINS.md](PLUGINS.md)** — the `bmadt` CLI command surface and the per-tool
  (Claude Code / Codex / OpenCode / Amp) file layouts.
- **[MILESTONE_1.md](MILESTONE_1.md)** — turn-key task checklist for the scaffold
  milestone, with acceptance criteria.

---

## References
- [BMAD-METHOD repository](https://github.com/bmad-code-org/BMAD-METHOD)
- [BMAD Workflow Map](https://docs.bmad-method.org/reference/workflow-map/)
- [How to Install BMAD](https://docs.bmad-method.org/how-to/install-bmad/)
