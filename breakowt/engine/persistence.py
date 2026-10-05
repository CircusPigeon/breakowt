"""Crash-safe JSON saves and purchase receipts, independent of the renderer."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def read_json(path):
    """Recover the previous good save when the primary file cannot be read."""
    path = Path(path)
    data = _read(path)
    return data if data is not None else _read(path.with_suffix(path.suffix + ".bak"))


def _replace(path, payload):
    fd, name = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, data):
    """Replace only complete files; keep a valid previous version as a backup.

    Exceptions are deliberately left to the caller so failed saves can be shown
    to the player and a purchase can be cancelled before anything is delivered.
    """
    path = Path(path)
    payload = json.dumps(data, indent=1, default=list) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = _read(path)
    if previous is not None:
        _replace(path.with_suffix(path.suffix + ".bak"), json.dumps(previous, indent=1) + "\n")
    _replace(path, payload)


def record_purchase(data, price, key, keep=True, run_id=None, day=None):
    """Record the charge and, for consumables, delivery in the same profile write."""
    purse = data.setdefault("purse", {})
    purse["spent"] = int(purse.get("spent", 0)) + price
    if keep and key and key not in purse.setdefault("owned", []):
        purse["owned"].append(key)
    receipt = None
    if not keep and key and run_id:
        receipt = {"id": uuid.uuid4().hex, "run": run_id, "day": day, "key": key}
        purse.setdefault("purchases", []).append(receipt)
    return receipt


def pending_purchases(data, flags):
    """Only replay deliveries missing from this run's restored checkpoint."""
    applied = set(flags.get("_purchases", []))
    run_id = flags.get("_run_id")
    return [r for r in data.get("purse", {}).get("purchases", [])
            if isinstance(r, dict) and r.get("run") == run_id and r.get("id") not in applied
            and r.get("key") in ("shells", "coffee") and isinstance(r.get("id"), str)]
