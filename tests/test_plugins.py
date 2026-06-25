
from plugins import bmadt, config, install

# --- config ---

def test_config_load_reads_toml_and_env(tmp_path, monkeypatch):
    cfgfile = tmp_path / "config.toml"
    cfgfile.write_text('base_url = "https://h"\nproject_id = "p1"\n')
    monkeypatch.setenv("BMADT_TOKEN", "tok123")
    cfg = config.load(path=cfgfile)
    assert cfg.base_url == "https://h"
    assert cfg.project_id == "p1"
    assert cfg.token == "tok123"
    assert cfg.api == "https://h/api/v1"


def test_config_flags_override(tmp_path):
    cfg = config.load(base_url="http://x", project_id="zzz", path=tmp_path / "missing.toml")
    assert cfg.base_url == "http://x"
    assert cfg.project_id == "zzz"


# --- file helpers ---

def test_collect_and_write_roundtrip(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "prd.md").write_text("# PRD")
    (tmp_path / "docs" / "x.png").write_bytes(b"\x89PNG")  # non-text, skipped
    files = bmadt.collect_files(tmp_path)
    assert "docs/prd.md" in files
    assert not any(k.endswith(".png") for k in files)

    out = tmp_path / "out"
    n = bmadt.write_files(out, files)
    assert n == len(files)
    assert (out / "docs" / "prd.md").read_text() == "# PRD"


# --- command functions against a stub client ---

class StubClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path):
        self.calls.append(("GET", path))
        return self.responses.get(("GET", path))

    def post(self, path, body=None):
        self.calls.append(("POST", path, body))
        return self.responses.get(("POST", path), {"ok": True})

    results = staticmethod(bmadt.Client.results)


def _cfg():
    return config.Config(base_url="http://h", project_id="P", token="t")


def test_cmd_get_story_by_label():
    client = StubClient({
        ("GET", "/stories/?project=P&label=2.3"):
            {"results": [{"id": "S", "label": "2.3", "title": "Login", "status": "draft"}]},
    })
    out = bmadt.cmd_get(client, _cfg(), type("A", (), {"kind": "story", "ref": "2.3"}))
    assert out["title"] == "Login"


def test_cmd_set_transitions_story():
    client = StubClient({
        ("GET", "/stories/?project=P&label=2.3"): {"results": [{"id": "S"}]},
    })
    bmadt.cmd_set(client, _cfg(), type("A", (), {"ref": "2.3", "status": "approved"}))
    assert ("POST", "/stories/S/transition/", {"to": "approved"}) in client.calls


def test_cmd_list_stories_compacts():
    client = StubClient({
        ("GET", "/stories/?project=P"):
            {"results": [{"label": "1.1", "title": "A", "status": "draft", "extra": 1}]},
    })
    rows = bmadt.cmd_list(client, _cfg(), type("A", (), {"kind": "stories", "status": None}))
    assert rows == [{"label": "1.1", "title": "A", "status": "draft"}]


# --- installer ---

def test_plan_claude_has_vendored_cli_and_block():
    files = install.plan("claude", "http://host", "PID")
    assert ".bmadt/bmadt.py" in files
    assert ".bmadt/config.py" in files
    assert 'project_id = "PID"' in files[".bmadt/config.toml"]
    assert "__append__CLAUDE.md" in files
    assert ".claude/commands/bmad.md" in files


def test_apply_writes_files_and_block_is_idempotent(tmp_path):
    files = install.plan("codex", "http://host", "PID")
    install.apply(files, tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text()
    assert install.BLOCK_START in agents and install.BLOCK_END in agents
    assert (tmp_path / ".bmadt" / "bmadt.py").exists()

    # second run replaces the block rather than duplicating it
    install.apply(install.plan("codex", "http://host", "PID"), tmp_path)
    agents2 = (tmp_path / "AGENTS.md").read_text()
    assert agents2.count(install.BLOCK_START) == 1


def test_opencode_plan_writes_config():
    files = install.plan("opencode", "http://host", "PID")
    assert "opencode.json" in files
    assert "bmad-next" in files["opencode.json"]


def test_upsert_block_preserves_surrounding_text():
    existing = "# My Agents\n\nkeep me\n"
    out = install._upsert_block(existing, "BLOCK")
    assert "keep me" in out
    assert "BLOCK" in out
