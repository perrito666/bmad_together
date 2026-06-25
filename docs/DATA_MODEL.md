# Data Model — ER Diagram

The model graph behind the platform. Tenant scoping flows from `Organization` down;
every artifact resolves to an org (and optionally a team + owner) for access control.

```mermaid
erDiagram
    User ||--o{ Membership : has
    Organization ||--o{ Membership : has
    Team ||--o{ Membership : has
    Organization ||--o{ Team : contains
    Organization ||--o{ Invitation : issues
    User ||--o{ Invitation : "invited_by"
    User ||--o{ APIToken : owns

    Organization ||--o{ Project : owns
    Team ||--o{ Project : "scopes (optional)"
    User ||--o{ Project : "owns"
    Project ||--|| CoreConfig : has
    Project ||--|| SprintStatus : has

    Project ||--o{ Artifact : contains
    Artifact ||--o{ ArtifactVersion : "snapshots"
    Artifact ||--o{ Attachment : has
    ArtifactVersion }o--|| User : "author"

    Project ||--o{ Epic : contains
    Epic ||--o{ Story : contains
    Story ||--o{ ArtifactVersion : "snapshots"
    Story }o--o| User : "assignee"

    Artifact }o--o| Story : "qa_gate targets (when type=qa_gate)"
    Artifact }o--o| Project : "prd/arch/ux link"

    User {
        uuid id PK
        string email
        string username
    }
    Organization {
        uuid id PK
        string name
        string slug
    }
    Team {
        uuid id PK
        uuid organization_id FK
        string name
        string slug
    }
    Membership {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        uuid team_id FK "nullable"
        string role "owner|admin|member|viewer"
    }
    Invitation {
        uuid id PK
        uuid organization_id FK
        uuid team_id FK "nullable"
        string email
        string role
        string token
        string status "pending|accepted|revoked|expired"
        datetime expires_at
    }
    APIToken {
        uuid id PK
        uuid user_id FK
        string name
        string prefix
        string hashed_key
        json scopes "reserved"
        datetime revoked_at "nullable"
    }
    Project {
        uuid id PK
        uuid organization_id FK
        uuid team_id FK "nullable"
        uuid owner_id FK
        string name
        string slug
    }
    Artifact {
        uuid id PK
        uuid project_id FK
        string type "brief|prd|architecture|..."
        string title
        string slug
        string status
        text body
        json data
        uuid current_version_id FK
    }
    ArtifactVersion {
        uuid id PK
        uuid artifact_id FK
        int number
        text body
        json data
        uuid author_id FK
        string message
        datetime created_at
    }
    Epic {
        uuid id PK
        uuid project_id FK
        int number
        string title
        string status
        json data
    }
    Story {
        uuid id PK
        uuid epic_id FK
        int number
        string title
        string status "draft|approved|in_progress|review|done|blocked"
        json acceptance_criteria
        json tasks
        text dev_notes
        json qa_results
        uuid assignee_id FK "nullable"
    }
```

## Notes

- **PKs are UUIDs** — opaque ids are friendlier for a multi-tenant REST API and the CLI.
- **`Artifact.data`** holds type-specific structure (see `DATA_SCHEMAS.md`); `Epic` and
  `Story` are promoted out of the generic `Artifact` table because they carry lifecycle
  and relationships.
- **Versioning** reuses `ArtifactVersion` for both `Artifact` and `Story` via a generic
  relation (or a parallel `StoryVersion` — decided at implementation; generic relation
  preferred to avoid duplication).
- **qa_gate** is stored as an `Artifact(type=qa_gate)` with a nullable FK to the `Story`
  it targets, keeping the QA history queryable alongside other artifacts.
- **Scoping invariant**: `Team.organization == Membership.organization`, and a
  `Project`/`Artifact` is visible to a user iff a matching `Membership` exists (team-scoped
  rows additionally require team membership). Enforced centrally in `TenantScopedViewSet`
  and mirrored in the web views.
