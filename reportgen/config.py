"""
Carga y expone la configuración global del proyecto; compatible con
Pydantic v1 ó v2 (+ pydantic-settings).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

# ── Compatibilidad dinámica ───────────────────────────────────────────────────
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore

    class _Base(BaseSettings):
        model_config: SettingsConfigDict = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "extra": "ignore",
        }

except ModuleNotFoundError:  # v1 fallback
    from pydantic import BaseSettings as _Base  # type: ignore

    class _Base(_Base):  # type: ignore[misc]
        class Config:  # noqa: D401
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"


class Settings(_Base):
    template_path: Path = Path("./inputs/Template.pptx")
    output_dir: Path = Path("./outputs")
    chapter_leader: str = "ANTHONY JAESSON ROJAS MUNARES"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


if TYPE_CHECKING:  # ayuda para linters
    settings: Settings = get_settings()
