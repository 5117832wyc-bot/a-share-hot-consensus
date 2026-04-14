"""从项目根 .env 注入环境变量（键已存在且非空则跳过）。"""
from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _ROOT / ".env"


def load_repo_dotenv() -> None:
    if not _ENV_PATH.is_file():
        return
    try:
        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if not key:
                    continue
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                existing = os.environ.get(key)
                if existing is not None and str(existing).strip() != "":
                    continue
                os.environ[key] = val
    except OSError:
        pass


def repo_root() -> Path:
    return _ROOT
