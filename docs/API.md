# REST API Contract

DRF API under `/api/v1/`. This is the contract the web UI and the `bmadt` CLI both
consume. OpenAPI schema is generated via drf-spectacular at `/api/schema/` with Swagger
UI at `/api/docs/`.

## Conventions

- **Media type**: `application/json`. Markdown bodies are plain strings in `body`.
- **IDs**: UUID strings.
- **Auth** (any of): session (web), `Authorization: Bearer <jwt>` (interactive),
  `Authorization: Token <pat>` (CLI/automation).
- **Pagination**: cursor pagination, `?limit=&cursor=`, envelope
  `{ "results": [...], "next": "url?", "previous": "url?" }`.
- **Filtering**: documented per endpoint (`?type=`, `?status=`, `?epic=`, `?assignee=`,
  `?q=` full-text).
- **Errors**: `{ "detail": "...", "code": "...", "errors": { "<field>": ["..."] }? }`
  with standard status codes (400 validation, 401 unauth, 403 scope, 404 not-found/hidden,
  409 invalid transition).
- **Tenant scoping**: every list/detail queryset is filtered to the caller's memberships.
  A row the caller can't see returns **404** (not 403) to avoid leaking existence.

## Auth & identity

```
POST /api/v1/auth/token/                 # JWT obtain (email+password)  -> {access, refresh}
POST /api/v1/auth/token/refresh/         # JWT refresh
GET  /api/v1/auth/me/                    # current user + memberships
GET/POST/DELETE /api/v1/auth/tokens/     # manage personal access tokens (PATs)
       # POST returns the raw token ONCE: {id, name, token, prefix}
POST /api/v1/invitations/{token}/accept/ # accept an invite -> creates Membership
```

## Tenancy

```
GET            /api/v1/orgs/                      # orgs the caller belongs to
GET            /api/v1/orgs/{id}/
GET/POST       /api/v1/orgs/{id}/teams/
GET/POST       /api/v1/orgs/{id}/invitations/    # owner/admin only
POST           /api/v1/orgs/{id}/invitations/{iid}/revoke/
GET            /api/v1/orgs/{id}/members/
```

> Org **creation** is staff-only (Django admin / restricted endpoint), per the invite-only
> model — there is no public `POST /orgs/`.

## Projects

```
GET/POST       /api/v1/projects/                 ?org=&team=
GET/PUT/DELETE /api/v1/projects/{id}/
GET/PUT        /api/v1/projects/{id}/config/     # CoreConfig
GET            /api/v1/projects/{id}/sprint-status/
POST           /api/v1/projects/{id}/import/     # multipart: BMAD docs/ bundle (zip)
GET            /api/v1/projects/{id}/export/     # -> zip of canonical docs/ tree
```

## Artifacts (generic, versioned)

```
GET/POST       /api/v1/projects/{id}/artifacts/  ?type=&status=&q=
GET/PUT/DELETE /api/v1/artifacts/{id}/
GET            /api/v1/artifacts/{id}/versions/        # list snapshots
GET            /api/v1/artifacts/{id}/versions/{n}/
GET            /api/v1/artifacts/{id}/diff/?from=&to=  # unified diff of body + data
POST           /api/v1/artifacts/{id}/attachments/
```

A `PUT` that changes `body`/`data` creates a new `ArtifactVersion` automatically and
advances `current_version`.

## Workflow (epics & stories)

```
GET/POST       /api/v1/projects/{id}/epics/
GET/PUT/DELETE /api/v1/epics/{id}/
GET/POST       /api/v1/epics/{id}/stories/
GET/PUT/DELETE /api/v1/stories/{id}/
POST           /api/v1/stories/{id}/transition/   {"to": "in_progress"}  # validated
GET            /api/v1/stories/{id}/versions/
POST           /api/v1/projects/{id}/next-story/   # SM helper: next draft after last done
```

`transition/` rejects illegal moves with **409** and a `code` of `invalid_transition`,
and enforces guards (e.g. `done` requires all tasks complete, when configured).

## Serializer sketches

```
ProjectSerializer:        id, org, team, owner, name, slug, description, created_at
ArtifactSerializer:       id, project, type, title, slug, status, body, data,
                          current_version, created_by, created_at, updated_at
ArtifactVersionSerializer:id, number, message, author, created_at  (body/data on detail)
EpicSerializer:           id, project, number, title, goal, status, data, story_count
StorySerializer:          id, epic, number, title, status, acceptance_criteria, tasks,
                          dev_notes, qa_results, assignee, data, created_at, updated_at
StoryTransitionSerializer:to            # validates against the state machine
```

Write serializers validate `data` against the per-type JSON schema (see `DATA_SCHEMAS.md`);
unknown types/fields are rejected.

## Permissions

- `IsAuthenticated` globally.
- `TenantScopedQuerysetMixin` filters every queryset to the caller's memberships.
- `RolePermission` maps HTTP method → required role:
  - read (GET): `viewer+`
  - write (POST/PUT/PATCH): `member+`
  - destructive (DELETE), org/team/invite management: `admin+` / `owner`
- Object-level check on detail routes re-verifies org/team scope (defense in depth).

## Example

```
GET /api/v1/projects/01J.../artifacts/?type=story&status=approved
Authorization: Token bmadt_8f2c...

200 OK
{
  "results": [
    { "id": "01J...", "type": "story", "title": "User can accept an invite",
      "status": "approved", "data": { "statement": {...}, "acceptance_criteria": [...] } }
  ],
  "next": null, "previous": null
}
```
