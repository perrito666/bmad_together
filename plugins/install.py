"""Generate per-tool plugin shims that point a repo's BMAD agents at bmad_together.

    python -m plugins.install --tool claude --project <id> [--base-url URL] [--dir .]
    python -m plugins.install --tool all --project <id>

Lays down a vendored copy of the bmadt CLI under .bmadt/, a config, and the tool's
native command/agent files (Claude Code, Codex, OpenCode, Amp). Tokens are NOT written
— each developer exports $BMADT_TOKEN. Re-running replaces a managed block, so it is
idempotent.
"""
from __future__ import annotations

import argparse
from pathlib import Path

TOOLS = ["claude", "codex", "opencode", "amp"]
CMD = "python .bmadt/bmadt.py"
BLOCK_START = "<!-- BMADT:START -->"
BLOCK_END = "<!-- BMADT:END -->"

_WORKFLOW = f"""\
## BMAD via bmad_together (`bmadt`)

This repository's BMAD artifacts live in **bmad_together**, not in local `docs/`
files. Use the `bmadt` CLI as the source of record. Authenticate once per shell:

    export BMADT_TOKEN=<your personal access token from the web UI>

Common commands:

    {CMD} whoami                      # verify auth
    {CMD} list stories --status approved
    {CMD} get story 2.3              # read a story (JSON)
    {CMD} next-story                 # the next story to implement
    {CMD} set story 2.3 --status in_progress
    {CMD} get prd                    # read the PRD / architecture / brief
    {CMD} export ./docs              # materialize the canonical docs/ tree
    {CMD} import ./docs              # push local docs/ back into the platform

When acting as a BMAD agent (SM/Dev/QA): read the relevant story with
`{CMD} get story <label>`, do the work, then update status with
`{CMD} set story <label> --status <next>`.
"""


def _vendor_files() -> dict[str, str]:
    here = Path(__file__).parent
    return {
        ".bmadt/bmadt.py": (here / "bmadt.py").read_text(),
        ".bmadt/config.py": (here / "config.py").read_text(),
    }


def _config_toml(base_url: str, project_id: str) -> str:
    return (
        f'base_url = "{base_url}"\n'
        f'project_id = "{project_id}"\n'
        "# token is read from $BMADT_TOKEN; never commit it.\n"
    )


def _upsert_block(existing: str, block: str) -> str:
    """Insert or replace the managed block within an existing file's text."""
    managed = f"{BLOCK_START}\n{block}\n{BLOCK_END}\n"
    if BLOCK_START in existing and BLOCK_END in existing:
        pre = existing.split(BLOCK_START)[0]
        post = existing.split(BLOCK_END, 1)[1]
        return f"{pre}{managed}{post}"
    sep = "" if not existing or existing.endswith("\n") else "\n"
    return f"{existing}{sep}\n{managed}"


def _claude_files() -> dict[str, str]:
    cmd_md = f"""\
---
description: Use bmad_together (bmadt) for BMAD artifacts
---

BMAD artifacts for this repo live in bmad_together. Use the `bmadt` CLI:

- Read a story: `{CMD} get story <label>`
- Next story to implement: `{CMD} next-story`
- Update status: `{CMD} set story <label> --status <next>`
- Read PRD/architecture/brief: `{CMD} get prd` / `architecture` / `brief`
- Sync docs locally: `{CMD} export ./docs`

$ARGUMENTS
"""
    return {".claude/commands/bmad.md": cmd_md}


def _opencode_files() -> dict[str, str]:
    import json

    conf = {
        "$schema": "https://opencode.ai/config.json",
        "command": {
            "bmad-next": {"template": f"{CMD} next-story", "description": "Next BMAD story"},
            "bmad-get": {"template": f"{CMD} get story $ARGUMENTS", "description": "Read a story"},
        },
    }
    return {"opencode.json": json.dumps(conf, indent=2) + "\n"}


def plan(tool: str, base_url: str, project_id: str) -> dict[str, str]:
    """Return the {path: content} files to write for a tool (managed-block aware)."""
    files = dict(_vendor_files())
    files[".bmadt/config.toml"] = _config_toml(base_url, project_id)

    if tool == "claude":
        files.update(_claude_files())
        files["__append__CLAUDE.md"] = _WORKFLOW
    elif tool == "codex":
        files["__append__AGENTS.md"] = _WORKFLOW
    elif tool == "amp":
        files["__append__AGENTS.md"] = _WORKFLOW
    elif tool == "opencode":
        files.update(_opencode_files())
        files["__append__AGENTS.md"] = _WORKFLOW
    else:
        raise ValueError(f"Unknown tool: {tool}")
    return files


def apply(files: dict[str, str], root: Path) -> list[str]:
    written = []
    for path, content in files.items():
        if path.startswith("__append__"):
            target = root / path.removeprefix("__append__")
            existing = target.read_text() if target.exists() else ""
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_upsert_block(existing, content))
        else:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        written.append(str(target.relative_to(root)))
    return written


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="plugins.install", description=__doc__.splitlines()[0])
    p.add_argument("--tool", required=True, choices=[*TOOLS, "all"])
    p.add_argument("--project", required=True)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--dir", default=".")
    args = p.parse_args(argv)

    root = Path(args.dir)
    tools = TOOLS if args.tool == "all" else [args.tool]
    all_written: list[str] = []
    for tool in tools:
        all_written += apply(plan(tool, args.base_url, args.project), root)

    print(f"Installed {', '.join(tools)} shim(s) into {root}/:")
    for path in sorted(set(all_written)):
        print(f"  {path}")
    print("\nNext: export BMADT_TOKEN=<token from the web UI>, then run "
          f"`{CMD} whoami`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
