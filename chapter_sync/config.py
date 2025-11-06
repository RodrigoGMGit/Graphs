from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _get_default_data_dir() -> str:
    """Get the default data directory path, handling executable mode."""
    if getattr(sys, "frozen", False):
        # Running as executable - use external files directory
        exec_dir = Path(sys.executable).resolve().parent
        return str(exec_dir / "files")
    else:
        # Running as script
        workspace_root = Path(__file__).resolve().parent.parent
        return str(workspace_root / "chapter_sync" / "files")


@dataclass
class AppConfig:
    data_dir: str = field(default_factory=_get_default_data_dir)
    cache_subdir: str = "cached_files"
    # chapter_leader: str = "RENE RUBEN PLAZ CABRERA"
    # chapter_leader_email: str = "rplaz@bcp.com.pe"
    chapter_leader: str = "Cesar Augusto Baldeón Ramirez"
    chapter_leader_email: str = "cesarbaldeon@bcp.com.pe"
    tmd_threshold: int = 13

    def load(self, path: str | None = None) -> None:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for k, v in data.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    @property
    def files_dir(self) -> str:
        return self.data_dir

    @property
    def cache_dir(self) -> str:
        return os.path.join(self.files_dir, self.cache_subdir)


config = AppConfig()
