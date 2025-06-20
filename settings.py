from __future__ import annotations
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "chapter_config.json"

try:
    _cfg = json.loads(CONFIG_PATH.read_text("utf-8"))
except Exception:
    _cfg = {}

DATA_ROOT = Path(_cfg.get("data_dir") or ROOT)


def get_months(root: str | Path | None = None) -> list[str]:
    pat = re.compile(r"^20\d{2} [01]\d$")
    base = Path(root) if root else DATA_ROOT
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and pat.match(p.name))


