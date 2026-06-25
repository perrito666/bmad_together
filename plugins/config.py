"""Configuration for the bmadt CLI.

Resolution order (later wins): defaults -> ./.bmadt/config.toml -> environment
-> explicit CLI flags. Token always comes from the environment ($BMADT_TOKEN) so it
never lands in a committed file. Stdlib-only, so this module can be vendored into any
repository alongside ``bmadt.py``.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(".bmadt/config.toml")
TOKEN_ENV = "BMADT_TOKEN"


@dataclass
class Config:
    base_url: str = "http://localhost:8000"
    project_id: str | None = None
    token: str | None = None

    @property
    def api(self) -> str:
        return self.base_url.rstrip("/") + "/api/v1"


def load(
    *, base_url: str | None = None, project_id: str | None = None, path: Path = CONFIG_PATH
) -> Config:
    cfg = Config()
    if path.exists():
        data = tomllib.loads(path.read_text())
        cfg.base_url = data.get("base_url", cfg.base_url)
        cfg.project_id = data.get("project_id", cfg.project_id)
    cfg.token = os.environ.get(TOKEN_ENV)
    if base_url:
        cfg.base_url = base_url
    if project_id:
        cfg.project_id = project_id
    return cfg
