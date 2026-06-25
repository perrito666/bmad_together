# bmad_together plugins

REST-based shims that let coding tools (Claude Code, Codex, OpenCode, Amp) use
bmad_together as the source of record for BMAD artifacts instead of local `docs/` files.

## Install into a target repo

```bash
python -m plugins.install --tool claude --project <project-id> --base-url https://your-host
# or every tool at once:
python -m plugins.install --tool all --project <project-id>
```

This writes, into the target repo:

- `.bmadt/bmadt.py` + `.bmadt/config.py` — a vendored, stdlib-only copy of the CLI.
- `.bmadt/config.toml` — `base_url` + `project_id` (no token).
- Tool files: `.claude/commands/bmad.md` + a managed block in `CLAUDE.md` (Claude),
  `AGENTS.md` (Codex/Amp), `opencode.json` + `AGENTS.md` (OpenCode).

Re-running replaces the managed `<!-- BMADT:START -->…END -->` block, so it is idempotent.

## Authenticate

Mint a personal access token in the web UI, then:

```bash
export BMADT_TOKEN=bmadt_xxx.yyy
python .bmadt/bmadt.py whoami
```

## CLI

```
bmadt whoami
bmadt project
bmadt list stories|epics|artifacts [--status S] [--type T]
bmadt get story 2.3 | get prd | get architecture | get brief
bmadt set story 2.3 --status in_progress
bmadt next-story
bmadt create-story --epic 2 --title "..." [--body-file draft.md]
bmadt export ./docs        # write the canonical docs/ tree locally
bmadt import ./docs        # push local docs/ back into the platform
```

The token is read from `$BMADT_TOKEN` and is never written to disk by the installer.
