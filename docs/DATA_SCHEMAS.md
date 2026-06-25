# Artifact `data` Schemas

Each `Artifact` (and the first-class `Epic` / `Story` models) stores type-specific
structured fields in a JSONB `data` column alongside the markdown `body`. This doc
defines the shape per artifact type, derived from the BMAD templates. These schemas
drive:

- form rendering in the web UI,
- serializer validation in the REST API,
- and the import/export mapping to/from BMAD `docs/` markdown.

Conventions: schemas are described as JSON. `?` marks optional fields. `[]` marks a
list. Every type also implicitly has the model-level fields (`title`, `status`,
`created_by`, timestamps) and a free-form markdown `body` for prose the structure
doesn't capture. Each type carries a `change_log[]` for human-readable history on
top of the immutable `ArtifactVersion` snapshots.

```
change_log entry := { date, version, description, author }
```

---

## brief — Project Brief (Analyst)

```json
{
  "problem_statement": "string",
  "proposed_solution": "string",
  "target_users": [{ "segment": "string", "description": "string" }],
  "goals": ["string"],
  "success_metrics": ["string"],
  "mvp_scope": { "in": ["string"], "out": ["string"] },
  "post_mvp_vision": "string?",
  "constraints": ["string"],
  "risks": [{ "risk": "string", "mitigation": "string?" }],
  "open_questions": ["string"],
  "change_log": []
}
```

## research — Market / Competitor Research (Analyst)

```json
{
  "research_type": "market | competitor | technical | user",
  "objectives": ["string"],
  "findings": [{ "title": "string", "detail": "string", "evidence": "string?" }],
  "competitors": [{ "name": "string", "strengths": ["string"], "weaknesses": ["string"] }],
  "recommendations": ["string"],
  "sources": [{ "label": "string", "url": "string?" }],
  "change_log": []
}
```

## brainstorm — Brainstorming Output (Analyst)

```json
{
  "techniques_used": ["string"],
  "ideas": [{ "text": "string", "theme": "string?", "rating": "int?" }],
  "themes": ["string"],
  "action_items": ["string"],
  "change_log": []
}
```

---

## prd — Product Requirements Document (PM)

The hub artifact. Epics are referenced here but live as first-class `Epic` rows.

```json
{
  "goals": ["string"],
  "background_context": "string",
  "functional_requirements":     [{ "id": "FR1",  "text": "string" }],
  "non_functional_requirements": [{ "id": "NFR1", "text": "string" }],
  "ux_design_goals": {
    "vision": "string?",
    "interaction_paradigms": ["string"],
    "core_screens": ["string"],
    "accessibility": "string?",
    "branding": "string?",
    "target_platforms": ["string"]
  },
  "technical_assumptions": {
    "repository_structure": "monorepo | polyrepo | string",
    "service_architecture": "string",
    "testing_requirements": "string",
    "additional": ["string"]
  },
  "epics": [{ "ref_id": "int", "number": "int", "title": "string", "goal": "string" }],
  "is_sharded": "bool",
  "change_log": []
}
```

> `epics[]` mirrors the linked `Epic` rows (FK graph is the source of truth; this
> array is a denormalized convenience for rendering/export).

## ux_spec — UX / Front-end Spec (UX Expert)

```json
{
  "overall_ux_goals": ["string"],
  "personas": [{ "name": "string", "description": "string" }],
  "information_architecture": "string",
  "user_flows": [{ "name": "string", "steps": ["string"], "diagram": "string?" }],
  "wireframe_refs": [{ "label": "string", "url": "string?" }],
  "component_library": "string?",
  "branding_style_guide": "string?",
  "accessibility_requirements": ["string"],
  "responsiveness": "string?",
  "change_log": []
}
```

## architecture — Architecture Document (Architect)

```json
{
  "introduction": "string",
  "high_level_architecture": {
    "technical_summary": "string",
    "platform": "string",
    "repository_structure": "string",
    "architecture_diagram": "string?"
  },
  "tech_stack": [
    { "category": "string", "technology": "string", "version": "string?", "purpose": "string" }
  ],
  "data_models": [{ "name": "string", "description": "string", "fields": ["string"] }],
  "components": [{ "name": "string", "responsibility": "string", "depends_on": ["string"] }],
  "api_spec": "string?",
  "database_schema": "string?",
  "source_tree": "string?",
  "coding_standards": ["string"],
  "test_strategy": "string?",
  "security": ["string"],
  "change_log": []
}
```

---

## epic — Epic (Scrum Master) — first-class `Epic` model

```json
{
  "goal": "string",
  "description": "string?",
  "stories": [{ "ref_id": "int", "number": "int", "title": "string", "status": "string" }],
  "change_log": []
}
```

## story — Story (Scrum Master / Dev / QA) — first-class `Story` model

The richest object: the SM writes the plan, the Dev fills `dev_agent_record`, the QA
agent fills `qa_results`. Lifecycle status is a model field (see state machine below).

```json
{
  "statement": { "as_a": "string", "i_want": "string", "so_that": "string" },
  "acceptance_criteria": [{ "id": "AC1", "text": "string" }],
  "tasks": [
    { "id": "T1", "text": "string", "done": false,
      "ac_refs": ["AC1"],
      "subtasks": [{ "text": "string", "done": false }] }
  ],
  "dev_notes": "string",
  "testing": { "standards": "string?", "locations": ["string"], "frameworks": ["string"] },
  "dev_agent_record": {
    "agent_model": "string?",
    "debug_log_refs": ["string"],
    "completion_notes": "string?",
    "file_list": ["string"]
  },
  "qa_results": "string?",
  "change_log": []
}
```

### Story status lifecycle

```
draft ──approve──▶ approved ──start──▶ in_progress ──submit──▶ review
                                            │                     │
                                            ▼                     ├─pass──▶ done
                                         blocked ◀──block──┐      └─reject─┐
                                            │              │              │
                                            └──unblock─────┴──────────────┘
```

- Transitions are validated server-side (`POST /stories/{id}/transition/`).
- `done` requires all `tasks[].done == true` (configurable per project).
- Entering `review` should have a linked `qa_gate` before reaching `done`
  (soft rule in v1; configurable).

## qa_gate — QA Gate / Assessment (QA / Test Architect)

```json
{
  "story_ref": "int",
  "gate_decision": "PASS | CONCERNS | FAIL | WAIVED",
  "reviewed_at": "datetime",
  "reviewer": "string",
  "top_issues": [
    { "severity": "low | medium | high", "finding": "string", "suggestion": "string?" }
  ],
  "nfr_validation": {
    "security":        { "status": "PASS|CONCERNS|FAIL", "notes": "string?" },
    "performance":     { "status": "PASS|CONCERNS|FAIL", "notes": "string?" },
    "reliability":     { "status": "PASS|CONCERNS|FAIL", "notes": "string?" },
    "maintainability": { "status": "PASS|CONCERNS|FAIL", "notes": "string?" }
  },
  "risk_summary": "string?",
  "waiver": { "active": false, "reason": "string?", "approved_by": "string?" },
  "change_log": []
}
```

---

## Project-level tracking (not artifacts)

### CoreConfig (`core-config.yaml`)

```json
{
  "prd": { "file": "docs/prd.md", "sharded": true, "epics_glob": "docs/prd/epic-*.md" },
  "architecture": { "file": "docs/architecture.md", "sharded": true },
  "stories": { "location": "docs/stories" },
  "qa": { "location": "docs/qa" },
  "dev_load_always_files": ["docs/architecture/coding-standards.md"],
  "markdown_exploder": true
}
```

### SprintStatus (`sprint-status.yaml`)

```json
{
  "epics": [
    { "number": 1, "title": "string", "status": "string",
      "stories": [{ "number": "1.1", "title": "string", "status": "string" }] }
  ],
  "generated_at": "datetime"
}
```

---

## Import / export mapping

| BMAD file (`docs/`)                | Platform object                         |
|------------------------------------|-----------------------------------------|
| `brief.md`                         | Artifact(type=brief)                    |
| `prd.md` (+ sharded `prd/*.md`)    | Artifact(type=prd) + Epic rows          |
| `architecture.md` (+ shards)       | Artifact(type=architecture)             |
| `front-end-spec.md` / `ux.md`      | Artifact(type=ux_spec)                  |
| `epic-{n}.md`                      | Epic(number=n)                          |
| `stories/{e}.{s}.story.md`         | Story(epic=e, number=s)                 |
| `qa/gates/{e}.{s}-*.yml`           | Artifact(type=qa_gate) → Story          |
| `sprint-status.yaml`               | SprintStatus                            |
| `core-config.yaml`                 | CoreConfig                              |

Markdown round-trips through a structured parser/serializer per type: section
headings ↔ `data` keys, with the residual prose preserved in `body`. Export
regenerates the canonical tree so a repo can drop back to file-based BMAD anytime.
