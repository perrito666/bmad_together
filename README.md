# bmad_together

A Django platform that turns [BMAD](https://github.com/bmad-code-org/BMAD-METHOD)
artifacts (briefs, PRDs, architecture docs, epics, stories, QA gates, …) into
first-class, multi-tenant database records with a REST API and a web UI — and lets
coding tools (Claude Code, Codex, OpenCode, Amp) read and write those artifacts
through the platform instead of loose markdown files.

The aim is to make BMAD produce **meaningful, queryable, governed documentation
after the fact**, scoped per user / team / organization.

## Status

**Milestone 1 (scaffold & accounts) is in.** Django project + `accounts` app
(orgs/teams/memberships/invitations/PATs), allauth (local + Google/GitHub SSO),
JWT + personal-access-token API auth, the invite-acceptance flow, tenant-scoping
primitives, admin, and CI. Tests pass on Postgres and sqlite.

## Development

```bash
# With Docker (recommended)
cp .env.example .env
make build && make up && make migrate
make superuser            # create an admin to provision orgs

# Or locally against your own Postgres
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgres://bmad:bmad@localhost:5432/bmad
python manage.py migrate && python manage.py runserver

make test                 # pytest (sqlite in-memory by default)
make lint                 # ruff
```

API docs at `/api/docs/`, admin at `/admin/`.

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
