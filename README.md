# bmad_together

A Django platform that turns [BMAD](https://github.com/bmad-code-org/BMAD-METHOD)
artifacts (briefs, PRDs, architecture docs, epics, stories, QA gates, …) into
first-class, multi-tenant database records with a REST API and a web UI — and lets
coding tools (Claude Code, Codex, OpenCode, Amp) read and write those artifacts
through the platform instead of loose markdown files.

The aim is to make BMAD produce **meaningful, queryable, governed documentation
after the fact**, scoped per user / team / organization.

## Status

**Milestones 1–2 are in.**

- **M1 — scaffold & accounts:** `accounts` app (orgs/teams/memberships/invitations/
  PATs), allauth (local + Google/GitHub SSO), JWT + PAT API auth, invite-acceptance
  flow, tenant-scoping primitives, admin, CI. uv-managed; one-command Docker startup.
- **M2 — domain models:** `projects` (Project/CoreConfig/SprintStatus), `core`
  (generic `Version` + `Versioned` mixin), `artifacts` (Artifact + Attachment), and
  `workflow` (Epic/Story with a validated status state machine). Admin, factories,
  model tests.

Tests pass on Postgres and sqlite (`make test`).

## Run it

### Docker (zero setup)

One command brings up Postgres + the app, runs migrations, and seeds an admin:

```bash
docker compose up --build      # or: make up
```

Then open:
- App / API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/api/docs/
- Admin: http://localhost:8000/admin/ — login `admin@example.com` / `admin`

`docker compose down` stops it; `docker compose down -v` also wipes the database.

### Local (uv)

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` +
`uv.lock`):

```bash
uv sync                                    # create .venv from the lockfile
export DATABASE_URL=postgres://bmad:bmad@localhost:5432/bmad
uv run python manage.py migrate
uv run python manage.py runserver

make test     # uv run pytest (sqlite in-memory unless DATABASE_URL is set)
make lint     # uv run ruff check .
```

## Planning docs

See:
- **[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** — full design: domain
  model, data model, REST API, web UI, plugin layer, milestones, decisions.
- **[docs/DATA_MODEL.md](docs/DATA_MODEL.md)** — ER diagram of the model graph and
  tenant-scoping invariants.
- **[docs/DATA_SCHEMAS.md](docs/DATA_SCHEMAS.md)** — structured `data` schema per
  artifact type, Story status state machine, BMAD `docs/` import/export mapping.
- **[docs/API.md](docs/API.md)** — REST contract: endpoints, serializers,
  permissions, errors.
- **[docs/PLUGINS.md](docs/PLUGINS.md)** — the `bmadt` CLI and per-tool shims for
  Claude Code, Codex, OpenCode, and Amp.
- **[docs/MILESTONE_1.md](docs/MILESTONE_1.md)** — turn-key scaffold checklist.

## At a glance

- **Backend**: Django 5 + Django REST Framework, PostgreSQL (JSONB).
- **UI**: Django templates + HTMX.
- **Auth**: django-allauth (local + Google/GitHub SSO); **invite-only** org membership.
- **Tenancy**: shared DB with row-level org / team / owner scoping.
- **Artifacts**: every document is versioned (whole-document immutable snapshots).
- **API auth**: JWT for interactive clients, personal access tokens for the CLI.
- **Plugins**: REST-based per-tool scripts (a `bmadt` CLI client) generated for
  Claude Code, Codex, OpenCode, and Amp.
