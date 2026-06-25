#!/usr/bin/env python3
"""bmadt — a thin REST client that lets coding tools use bmad_together as the source
of record for BMAD artifacts instead of local docs/ files.

Stdlib only (urllib), so it can be vendored into any repo. Auth via $BMADT_TOKEN.

Examples:
    bmadt whoami
    bmadt list stories --status approved
    bmadt get story 2.3
    bmadt get prd
    bmadt set story 2.3 --status in_progress
    bmadt next-story
    bmadt export ./docs
    bmadt import ./docs
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from . import config as cfg_mod
except ImportError:  # running as a vendored script (python .bmadt/bmadt.py)
    import config as cfg_mod

TEXT_SUFFIXES = {".md", ".markdown", ".yaml", ".yml", ".txt", ".json"}


class ApiError(RuntimeError):
    pass


class Client:
    def __init__(self, cfg: cfg_mod.Config):
        self.cfg = cfg

    def _request(self, method: str, path: str, body: dict | None = None):
        url = path if path.startswith("http") else f"{self.cfg.api}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cfg.token:
            req.add_header("Authorization", f"Token {self.cfg.token}")
        try:
            with urllib.request.urlopen(req) as resp:  # noqa: S310 - configured base URL
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if "application/json" in ctype:
                    return json.loads(raw) if raw else None
                return raw
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise ApiError(f"HTTP {e.code} {method} {url}\n{detail}") from e
        except urllib.error.URLError as e:
            raise ApiError(f"Cannot reach {url}: {e.reason}") from e

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, body=None):
        return self._request("POST", path, body or {})

    def patch(self, path, body):
        return self._request("PATCH", path, body)

    # results envelope helper
    @staticmethod
    def results(payload):
        return payload["results"] if isinstance(payload, dict) and "results" in payload else payload


# --- file helpers (for import/export) ---

def collect_files(root: Path) -> dict[str, str]:
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
            files[str(p.relative_to(root))] = p.read_text(encoding="utf-8", errors="replace")
    return files


def write_files(root: Path, files: dict[str, str]) -> int:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return len(files)


# --- command implementations ---

def _need_project(cfg):
    if not cfg.project_id:
        raise ApiError("No project configured. Set project_id in .bmadt/config.toml "
                       "or pass --project.")
    return cfg.project_id


def cmd_whoami(client, cfg, args):
    me = client.get("/auth/me/")
    return f"{me['email']} — {len(me['memberships'])} membership(s)"


def cmd_project(client, cfg, args):
    pid = _need_project(cfg)
    return client.get(f"/projects/{pid}/")


def cmd_list(client, cfg, args):
    pid = _need_project(cfg)
    if args.kind == "epics":
        return client.results(client.get(f"/projects/{pid}/epics/"))
    if args.kind == "artifacts":
        q = f"?project={pid}" + (f"&type={args.type}" if args.type else "")
        return client.results(client.get(f"/artifacts/{q}"))
    # stories
    q = f"?project={pid}" + (f"&status={args.status}" if args.status else "")
    rows = client.results(client.get(f"/stories/{q}"))
    return [{"label": r["label"], "title": r["title"], "status": r["status"]} for r in rows]


def cmd_get(client, cfg, args):
    pid = _need_project(cfg)
    if args.kind == "story":
        rows = client.results(client.get(f"/stories/?project={pid}&label={args.ref}"))
        if not rows:
            raise ApiError(f"No story {args.ref} in project.")
        return rows[0]
    # artifact by type (prd, architecture, brief, ux_spec, research, qa_gate)
    rows = client.results(client.get(f"/projects/{pid}/artifacts/?type={args.kind}"))
    if not rows:
        raise ApiError(f"No {args.kind} artifact in project.")
    return rows[0]


def cmd_set(client, cfg, args):
    pid = _need_project(cfg)
    rows = client.results(client.get(f"/stories/?project={pid}&label={args.ref}"))
    if not rows:
        raise ApiError(f"No story {args.ref}.")
    sid = rows[0]["id"]
    return client.post(f"/stories/{sid}/transition/", {"to": args.status})


def cmd_next_story(client, cfg, args):
    pid = _need_project(cfg)
    res = client.post(f"/projects/{pid}/next-story/")
    return res if res else "No story ready to pick up."


def cmd_create_story(client, cfg, args):
    epic_rows = client.results(client.get(f"/projects/{cfg.project_id}/epics/"))
    epic = next((e for e in epic_rows if e["number"] == args.epic), None)
    if epic is None:
        raise ApiError(f"No epic {args.epic} in project.")
    body = {"title": args.title}
    if args.body_file:
        body["body"] = Path(args.body_file).read_text()
    return client.post(f"/epics/{epic['id']}/stories/", body)


def cmd_export(client, cfg, args):
    pid = _need_project(cfg)
    payload = client.get(f"/projects/{pid}/export/?format=json")
    n = write_files(Path(args.dir), payload["files"])
    return f"Wrote {n} file(s) to {args.dir}"


def cmd_import(client, cfg, args):
    pid = _need_project(cfg)
    files = collect_files(Path(args.dir))
    if not files:
        raise ApiError(f"No importable files under {args.dir}")
    summary = client.post(f"/projects/{pid}/import/", {"files": files})
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bmadt", description=__doc__.splitlines()[0])
    p.add_argument("--base-url")
    p.add_argument("--project")
    p.add_argument("--json", action="store_true", help="raw JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("project").set_defaults(func=cmd_project)
    sub.add_parser("next-story").set_defaults(func=cmd_next_story)

    pl = sub.add_parser("list")
    pl.add_argument("kind", choices=["stories", "epics", "artifacts"])
    pl.add_argument("--status")
    pl.add_argument("--type")
    pl.set_defaults(func=cmd_list)

    pg = sub.add_parser("get")
    pg.add_argument(
        "kind", help="story | prd | architecture | brief | ux_spec | research | qa_gate"
    )
    pg.add_argument("ref", nargs="?", help="story label, e.g. 2.3")
    pg.set_defaults(func=cmd_get)

    ps = sub.add_parser("set")
    ps.add_argument("kind", choices=["story"])
    ps.add_argument("ref")
    ps.add_argument("--status", required=True)
    ps.set_defaults(func=cmd_set)

    pc = sub.add_parser("create-story")
    pc.add_argument("--epic", type=int, required=True)
    pc.add_argument("--title", required=True)
    pc.add_argument("--body-file")
    pc.set_defaults(func=cmd_create_story)

    pe = sub.add_parser("export")
    pe.add_argument("dir")
    pe.set_defaults(func=cmd_export)

    pi = sub.add_parser("import")
    pi.add_argument("dir")
    pi.set_defaults(func=cmd_import)

    return p


def render(result, as_json: bool) -> str:
    if isinstance(result, str):
        return result
    if as_json or isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, ensure_ascii=False)
    return str(result)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = cfg_mod.load(base_url=args.base_url, project_id=args.project)
    if not cfg.token:
        print(f"warning: ${cfg_mod.TOKEN_ENV} is not set; requests will be unauthenticated.",
              file=sys.stderr)
    client = Client(cfg)
    try:
        result = args.func(client, cfg, args)
    except ApiError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(render(result, args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
