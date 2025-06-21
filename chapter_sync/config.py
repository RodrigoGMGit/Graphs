from __future__ import annotations
from dataclasses import dataclass
import json
import os

@dataclass
class AppConfig:
    data_dir: str = "./files"
    cache_subdir: str = "cached_files"
    chapter_leader: str = "RENE RUBEN PLAZ CABRERA"
    chapter_leader_email: str = "rplaz@bcp.com.pe"
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
