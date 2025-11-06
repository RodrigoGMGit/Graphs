"""PySide6 GUI variant for ChapterSync.

This package hosts the Qt-based user interface that mirrors the
DearPyGUI implementation.  It is intentionally separated so both
GUIs can coexist during A/B testing and gradual migration.
"""

from __future__ import annotations

from chapter_sync.gui_qt.main import main, run

__all__ = ["main", "run"]
