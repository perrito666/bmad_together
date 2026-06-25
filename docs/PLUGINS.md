# Plugin Layer — `bmadt` CLI + per-tool shims

The plugins make the platform the system of record for BMAD artifacts, so coding
tools read/write through the REST API instead of local `docs/` markdown. The design
is **REST-only**: one shared CLI client (`bmadt`) plus thin per-tool config that
points each tool's BMAD agents at `bmadt`.

```
plugins/
├── common/                 # the bmadt CLI + REST client + auth/config
├── claude/                 # generator for Claude Code files
├── codex/                  # generator for Codex files
├── opencode/               # generator for OpenCode files
└── amp/                    # generator for Amp files
```

## Install / generate

```
python -m plugins.install --tool claude --project <project-id> [--base-url URL]
```

Writes the tool-specific files into the current repo and a shared `.bmadt/config.toml`.
`--tool all` lays down every tool's shims.

## `.bmadt/config.toml` (per repo)

```toml
base_url   = "https://bmad-together.example.com"
project_id = "01J..."          # which Project this repo maps to
# token is read from $BMADT_TOKEN, never written here
```

## `bmadt` command surface

A thin, scriptable wrapper over `/api/v1/`. Outputs markdown by default (so an agent
can read it) or `--json` for scripting. Auth via `$BMADT_TOKEN` (a personal access
token).

```
bmadt whoami
bmadt project show

# read
bmadt list stories [--status approved] [--epic 2]
bmadt list epics
bmadt get story 2.3                 # renders the story as markdown
bmadt get prd | architecture | brief | ux_spec
bmadt get qa-gate 2.3

# write / update
bmadt set story 2.3 --status in_progress
bmadt update story 2.3 --task T1 --done
bmadt update story 2.3 --dev-notes-file notes.md --file-list "a.py,b.py"
bmadt push prd --file docs/prd.md          # parse markdown → structured create/update
bmadt pull architecture --out docs/        # write canonical markdown locally

# create
bmadt create story --epic 2 --title "..." --from-file draft.md
bmadt create qa-gate 2.3 --decision CONCERNS --from-file gate.yml

# sync the whole repo
bmadt import ./docs                  # bulk ingest a BMAD docs/ tree
bmadt export ./docs                  # regenerate the canonical tree
```

Every command is tenant-scoped to the token's user; the server enforces org/team
access. Status transitions go through the validated `/stories/{id}/transition/`
endpoint, not raw field writes.

## Per-tool shims

Each generator emits the tool's native config so its BMAD personas call `bmadt`
instead of touching files. The persona prompts (SM/Dev/QA/etc.) are rewritten to:
"read the story with `bmadt get story X.Y`; when done, update it with
`bmadt set/update story ...`" — same workflow, platform-backed.

### Claude Code (`plugins/claude`)
- `.claude/commands/bmad-*.md` — slash commands wrapping `bmadt` (e.g. `/bmad-story`,
  `/bmad-next-story`, `/bmad-qa-gate`).
- `.claude/agents/*.md` — SM/Dev/QA agent defs pointed at `bmadt`.
- Appends a `## BMAD (bmad_together)` section to `CLAUDE.md` documenting the workflow.

### Codex (`plugins/codex`)
- `AGENTS.md` — instructions + `bmadt` command recipes per phase.
- Optional `.codex/` command snippets.

### OpenCode (`plugins/opencode`)
- `opencode.json` — agent/command entries that invoke `bmadt`.
- `AGENTS.md` workflow notes.

### Amp (`plugins/amp`)
- `AGENTS.md` — `bmadt` recipes.
- Amp toolbox/command entries calling `bmadt`.

## Auth setup (per developer)

1. In the web UI, create a **personal access token** (named, revocable).
2. `export BMADT_TOKEN=...` (shell profile / direnv / CI secret).
3. Run the generator once per repo; commit the shims (not the token).

The token is scoped to the developer's org memberships; revoking it in the UI
immediately cuts off the CLI and every tool using it.
