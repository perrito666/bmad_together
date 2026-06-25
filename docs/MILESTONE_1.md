# Milestone 1 — Scaffold & Accounts (turn-key checklist)

> **Status: implemented.** Project skeleton, dev/test/prod settings split, Docker
> Compose + Dockerfile + Makefile, the `accounts` app (User/Org/Team/Membership/
> Invitation/APIToken), allauth (local + Google/GitHub), JWT + PAT auth, the
> invite-acceptance flow, scoping primitives, admin, GitHub Actions CI, and the
> accounts test suite are all in. Verified: migrations apply on Postgres and the
> suite is green on both Postgres and sqlite. Remaining polish: tighten the
> drf-spectacular schema warnings and add a SessionStart hook (both optional).

Goal: a running Django project with Postgres, the `accounts` app (orgs/teams/
memberships/invitations/PATs), allauth auth (local + SSO), the invite-acceptance flow,
admin, and green CI. This is the foundation milestone 2+ build on.

## 1. Project skeleton
- [ ] `pyproject.toml` — deps: `django`, `djangorestframework`, `drf-spectacular`,
      `django-allauth`, `djangorestframework-simplejwt`, `psycopg[binary]`,
      `django-environ`, `gunicorn`; dev: `pytest-django`, `factory-boy`, `ruff`,
      `pre-commit`. Configure ruff + pytest here.
- [ ] `manage.py`, `config/` package with `settings/{base,dev,prod}.py`, `urls.py`,
      `asgi.py`, `wsgi.py`.
- [ ] Settings: env-driven (`django-environ`), `DATABASES` → Postgres, installed apps,
      DRF + spectacular + allauth + simplejwt config, `AUTH_USER_MODEL = "accounts.User"`.
- [ ] `.env.example`, `.gitignore`, `.dockerignore`.

## 2. Local dev environment
- [ ] `compose.yaml` — `db` (postgres:16) + `web` services, volumes, healthcheck.
- [ ] `Dockerfile` for the web image.
- [ ] `Makefile` (or `just`) targets: `up`, `migrate`, `test`, `lint`, `superuser`.
- [ ] README dev-setup section (clone → `cp .env.example .env` → `make up` → `make migrate`).

## 3. accounts app
- [ ] Custom `User(AbstractUser)` with email login (UUID pk).
- [ ] `Organization`, `Team`, `Membership(role)` models + constraints
      (`Team.organization == Membership.organization`; unique `(user, org, team)`).
- [ ] `Invitation` model (token, status, expiry) + manager helpers.
- [ ] `APIToken` model (prefix + hashed key; raw shown once on create).
- [ ] Migrations.
- [ ] Django admin registrations for all of the above.
- [ ] `factory_boy` factories for tests.

## 4. Auth (allauth + JWT + PAT)
- [ ] django-allauth wired: local email/password + Google + GitHub providers
      (provider keys via env; SSO optional in dev).
- [ ] simplejwt endpoints (`/api/v1/auth/token/`, `/refresh/`).
- [ ] Custom DRF `TokenAuthentication` for PATs (constant-time hashed lookup,
      `last_used_at` update, revocation check).
- [ ] `/api/v1/auth/me/` and PAT management endpoints.

## 5. Invitation flow
- [ ] `POST /orgs/{id}/invitations/` (owner/admin) → creates signed, expiring invite.
- [ ] Pluggable email backend (console in dev) sends the invite link.
- [ ] `POST /invitations/{token}/accept/` → validates token, creates `Membership`,
      marks invite accepted; handles expired/revoked/already-member.
- [ ] Staff-only org creation path (admin is enough for v1).

## 6. Scoping primitives (used everywhere later)
- [ ] `TenantScopedQuerysetMixin` + `RolePermission` (skeleton, unit-tested against
      accounts models so milestone 3 can reuse them).

## 7. CI & quality gates
- [ ] GitHub Actions: ruff + pytest against a Postgres service.
- [ ] `pre-commit` config (ruff format + lint).
- [ ] Optional: a SessionStart hook so web sessions can run tests/lint
      (see the `session-start-hook` skill).

## Acceptance criteria
- `make up && make migrate` brings up the stack; `make test` is green.
- A superuser can create an org + team in admin and issue an invitation.
- A second user can accept the invite (link) and gets the right `Membership`.
- A user can mint a PAT and call `GET /api/v1/auth/me/` with `Authorization: Token ...`.
- `GET /api/docs/` serves the (currently auth-only) OpenAPI UI.
- Lint + tests pass in CI.

## Out of scope (later milestones)
- Artifact/Epic/Story models and versioning → **M2**.
- Artifact REST endpoints + tenant-scoped viewsets in anger → **M3**.
- Web UI beyond allauth's templates → **M4**.
- Import/export and `bmadt`/plugins → **M5–M6**.
