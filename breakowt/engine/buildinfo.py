"""Which commit this copy of the game was checked out at, shown small on the title screen so a bug
report can say exactly what it ran. Read straight from .git (no git executable needed)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_id() -> str:
    git = ROOT / ".git"
    try:
        head = (git / "HEAD").read_text().strip()
        if not head.startswith("ref:"):
            return head[:7]                      # detached HEAD: the hash itself
        ref = head.split(" ", 1)[1].strip()
        loose = git / ref
        if loose.exists():
            return loose.read_text().strip()[:7]
        for line in (git / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line[:7]
    except OSError:
        pass
    return ""
