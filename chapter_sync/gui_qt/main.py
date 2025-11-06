"""Application bootstrap for the PySide6 ChapterSync GUI."""

from __future__ import annotations

import sys
from typing import Sequence

from PySide6.QtWidgets import QApplication

from chapter_sync.gui_qt.controller import ChapterSyncController
from chapter_sync.gui_qt.widgets import MainWindow


def _ensure_application(argv: Sequence[str] | None = None) -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)
        app.setApplicationName("ChapterSync")
        app.setOrganizationName("BCP")
        app.setOrganizationDomain("bcp.com.pe")
    return app  # type: ignore[return-value]


def run(argv: Sequence[str] | None = None) -> int:
    """Entrypoint used from code or CLI.

    Returns the Qt event loop exit code so callers can exit accordingly.
    """

    app = _ensure_application(argv)
    window = MainWindow()
    controller = ChapterSyncController(window)
    window.controller = controller  # type: ignore[attr-defined]
    window.show()
    return app.exec()


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - thin wrapper
    return run(argv)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    sys.exit(main())
