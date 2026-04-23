from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set

from hot_consensus.env import repo_root


def state_path() -> Path:
    p = os.getenv("HC_STATE_JSON", "").strip()
    if p:
        return Path(p).expanduser()
    return repo_root() / "hot_consensus_state.json"


def load_state() -> Dict[str, Any]:
    path = state_path()
    if not path.is_file() or path.stat().st_size == 0:
        return {
            "version": 2,
            "cls_seen": [],
            "last_push_ts": 0.0,
            "last_signature": "",
            "last_snap_hash": "",
            "last_auction_push_ts": 0.0,
            "last_pre_pm_digest_date": "",
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {
                "version": 2,
                "cls_seen": [],
                "last_push_ts": 0.0,
                "last_signature": "",
                "last_snap_hash": "",
                "last_auction_push_ts": 0.0,
                "last_pre_pm_digest_date": "",
            }
        data.setdefault("version", 1)
        data.setdefault("cls_seen", [])
        data.setdefault("last_push_ts", 0.0)
        data.setdefault("last_signature", "")
        data.setdefault("last_snap_hash", "")
        data.setdefault("last_auction_push_ts", 0.0)
        data.setdefault("last_pre_pm_digest_date", "")
        if int(data.get("version", 1)) < 2:
            data["version"] = 2
        return data
    except (json.JSONDecodeError, OSError):
        return {
            "version": 2,
            "cls_seen": [],
            "last_push_ts": 0.0,
            "last_signature": "",
            "last_snap_hash": "",
            "last_auction_push_ts": 0.0,
            "last_pre_pm_digest_date": "",
        }


def save_state(data: Dict[str, Any]) -> None:
    path = state_path()
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    tmp.replace(path)


def cls_seen_set(state: Dict[str, Any]) -> Set[str]:
    raw = state.get("cls_seen")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x}


def trim_seen(state: Dict[str, Any], max_keep: int = 8000) -> None:
    lst = state.get("cls_seen")
    if isinstance(lst, list) and len(lst) > max_keep:
        state["cls_seen"] = lst[-max_keep:]
