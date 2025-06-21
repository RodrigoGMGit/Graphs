"""ChapterSync package."""

from __future__ import annotations

import os

from .config import config

# Cargar configuración inicial desde variable de entorno
config.load(os.environ.get("CHAPTERSYNC_CONFIG"))

__all__ = ["config"]

