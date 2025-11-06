"""Application logic for the PySide6 GUI."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

from chapter_sync import graphs, presentation

from chapter_sync.gui_qt.widgets import MainWindow, ProfilePanel, WorkflowPanel


# ╔══════════════════ CONSTANTES COMPARTIDAS ════════════════════════════════╗
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
EXEC_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else APP_DIR
CONFIG_PATH = EXEC_DIR / "chapter_config.json"
FILES_DIR_DEMO = EXEC_DIR / "files"
OUTPUTS_DIR = EXEC_DIR / "outputs" if getattr(sys, "frozen", False) else APP_DIR / "outputs"

EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$")


@dataclass
class Profile:
    name: str
    email: str
    validated: bool = False


def load_config() -> tuple[list[Profile], str]:
    if not CONFIG_PATH.exists():
        return [], ""
    try:
        data = json.loads(CONFIG_PATH.read_text("utf-8"))
        profiles = [Profile(**p) for p in data.get("profiles", [])]
        return profiles, data.get("active", "")
    except Exception:
        return [], ""


def save_config(active_email: str, profiles: list[Profile]) -> None:
    payload = {
        "active": active_email,
        "profiles": [asdict(p) for p in profiles],
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")


# ╔══════════════════ WORKER PARA GENERAR PPT ═══════════════════════════════╗
class WorkerSignals(QObject):
    finished = Signal(bool, str, object, object)
    log = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()


class PresentationWorker(QRunnable):
    def __init__(self, chapter_leader: str, email: str, data_dir: str):
        super().__init__()
        self.chapter_leader = chapter_leader
        self.email = email
        self.data_dir = data_dir
        self.signals = WorkerSignals()

    def run(self) -> None:  # pragma: no cover - executed in worker thread
        import matplotlib

        matplotlib.use("Agg", force=True)

        prev_warn = getattr(graphs, "_warn", None)
        graphs._warn = lambda m: self.signals.log.emit(m, "warn")  # type: ignore[attr-defined]

        try:
            self._configure_graphs()
            self._maybe_download_files()
            presentation.main()
            ppt = self._pick_latest_presentation()
            if ppt is None:
                self.signals.finished.emit(False, "No se generó .pptx", None, None)
                return
            self.signals.finished.emit(
                True,
                "Presentación generada exitosamente.",
                str(ppt.parent),
                str(ppt),
            )
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(f"Error durante la generación: {exc}", "error")
            self.signals.finished.emit(False, f"Error: {exc}", None, None)
        finally:
            if prev_warn is not None:
                graphs._warn = prev_warn  # type: ignore[attr-defined]

    def _configure_graphs(self) -> None:
        graphs.config.chapter_leader = self.chapter_leader
        graphs.config.chapter_leader_email = self.email
        graphs.CHAPTER_LEADER = self.chapter_leader
        graphs.CHAPTER_LEADER_EMAIL = self.email
        graphs.CL_NORM = graphs.normalize_name(self.chapter_leader)
        graphs.config.data_dir = self.data_dir
        graphs.DATA_DIR = self.data_dir
        graphs.FILES_DIR = self.data_dir
        graphs.CACHE_DIR = os.path.join(self.data_dir, graphs.CACHE_SUBDIR)

    def _maybe_download_files(self) -> None:
        try:
            project_root = Path(__file__).resolve().parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from chapter_sync.file_processor import check_and_download_if_needed

            class GUILogHandler(logging.Handler):
                def __init__(self, outer: PresentationWorker) -> None:
                    super().__init__()
                    self.outer = outer

                def emit(self, record: logging.LogRecord) -> None:
                    msg = self.format(record)
                    if record.levelno >= logging.ERROR:
                        level = "error"
                    elif record.levelno >= logging.WARNING:
                        level = "warn"
                    else:
                        level = "info"
                    self.outer.signals.log.emit(msg, level)

            gui_handler = GUILogHandler(self)
            gui_handler.setFormatter(logging.Formatter("%(message)s"))

            file_processor_logger = logging.getLogger("chapter_sync.file_processor")
            file_downloading_logger = logging.getLogger("file_downloading.get_files")

            for logger in (file_processor_logger, file_downloading_logger):
                logger.setLevel(logging.INFO)
                if gui_handler not in logger.handlers:
                    logger.addHandler(gui_handler)

            check_and_download_if_needed(Path(self.data_dir))
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(
                f"Error al verificar/descargar archivos: {exc}. Continuando con archivos existentes.",
                "warn",
            )

    def _pick_latest_presentation(self) -> Optional[Path]:
        source_dir = OUTPUTS_DIR
        pptxs = list(source_dir.glob("*.pptx"))
        if not pptxs:
            return None
        return max(pptxs, key=lambda p: p.stat().st_mtime)


# ╔══════════════════ CONTROLADOR PRINCIPAL ════════════════════════════════╗
class ChapterSyncController(QObject):
    """Connects widgets with the business logic."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.profile_panel: ProfilePanel = window.profile_panel
        self.workflow_panel: WorkflowPanel = window.workflow_panel
        self.thread_pool = QThreadPool.globalInstance()

        self.profiles, self.active_email = load_config()
        self.edit_mode: Optional[str] = None  # "new" | "edit" | None
        self.output_dir: Optional[str] = None
        self.output_ppt: Optional[str] = None
        self.progress_dialog: Optional[QProgressDialog] = None

        self._bind_signals()
        self._refresh_profiles()
        self._sync_demo_state(self.workflow_panel.demo_checkbox.isChecked())

    # ── Signal wiring ------------------------------------------------------
    def _bind_signals(self) -> None:
        self.profile_panel.profile_selected.connect(self._on_profile_selected)
        self.profile_panel.create_requested.connect(self._on_new_profile)
        self.profile_panel.edit_requested.connect(self._on_edit_profile)
        self.profile_panel.delete_requested.connect(self._on_delete_profile)
        self.profile_panel.cancel_requested.connect(self._on_cancel_edit)

        self.workflow_panel.demo_checkbox.toggled.connect(self._sync_demo_state)
        self.workflow_panel.browse_button.clicked.connect(self._on_browse_folder)
        self.workflow_panel.generate_button.clicked.connect(self._on_generate)
        self.workflow_panel.open_folder_button.clicked.connect(self._on_open_folder)
        self.workflow_panel.open_ppt_button.clicked.connect(self._on_open_ppt)

    # ── Perfil management ---------------------------------------------------
    def _refresh_profiles(self) -> None:
        combo = self.profile_panel.profile_combo
        combo.blockSignals(True)
        combo.clear()
        for profile in self.profiles:
            combo.addItem(profile.name, profile.email)

        if self.profiles:
            active_profile = self._profile_by_email(self.active_email) or self.profiles[0]
            self.active_email = active_profile.email
            index = combo.findText(active_profile.name)
            combo.setCurrentIndex(index if index >= 0 else 0)
            self.window.statusBar().showMessage(f"Perfil activo: {active_profile.name}")
        else:
            self.active_email = ""
            self.window.statusBar().showMessage("Sin perfiles configurados")
        combo.blockSignals(False)

    def _profile_by_email(self, email: str) -> Optional[Profile]:
        return next((p for p in self.profiles if p.email == email), None)

    def _on_profile_selected(self, name: str) -> None:
        profile = next((p for p in self.profiles if p.name == name), None)
        if profile is None:
            return
        self.active_email = profile.email
        self.window.statusBar().showMessage(f"Perfil activo: {profile.name}")
        self._toggle_edit_form(False)

    def _on_new_profile(self) -> None:
        self.edit_mode = "new"
        self._toggle_edit_form(True, name="", email="")
        self.profile_panel.name_edit.setFocus()

    def _on_edit_profile(self) -> None:
        if not self.active_email:
            QMessageBox.information(self.window, "ChapterSync", "No hay perfil seleccionado.")
            return
        profile = self._profile_by_email(self.active_email)
        if profile is None:
            return
        self.edit_mode = "edit"
        self._toggle_edit_form(True, profile.name, profile.email)
        self.profile_panel.name_edit.setFocus()

    def _on_delete_profile(self) -> None:
        if not self.active_email:
            return
        profile = self._profile_by_email(self.active_email)
        if profile is None:
            return
        confirm = QMessageBox.question(
            self.window,
            "Eliminar perfil",
            f"¿Eliminar el perfil '{profile.name}'?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.profiles = [p for p in self.profiles if p.email != self.active_email]
        self.active_email = self.profiles[0].email if self.profiles else ""
        save_config(self.active_email, self.profiles)
        self._toggle_edit_form(False)
        self._refresh_profiles()
        self.workflow_panel.append_log(f"Perfil '{profile.name}' eliminado.")

    def _on_cancel_edit(self) -> None:
        self.edit_mode = None
        self._toggle_edit_form(False)

    def _toggle_edit_form(self, visible: bool, name: str = "", email: str = "") -> None:
        panel = self.profile_panel
        panel.name_edit.setVisible(visible)
        panel.email_edit.setVisible(visible)
        panel.info_label.setVisible(visible)
        panel.cancel_button.setVisible(visible)
        if visible:
            panel.name_edit.setText(name)
            panel.email_edit.setText(email)
        else:
            panel.name_edit.clear()
            panel.email_edit.clear()
        self.edit_mode = None if not visible else self.edit_mode

    # ── Workflow interactions -----------------------------------------------
    def _sync_demo_state(self, checked: bool) -> None:
        self.workflow_panel.path_edit.setEnabled(not checked)
        if checked:
            self.workflow_panel.path_edit.clear()

    def _on_browse_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self.window,
            "Selecciona la carpeta de datos",
            str(EXEC_DIR),
        )
        if directory:
            self.workflow_panel.path_edit.setText(directory)

    def _current_name_email(self) -> tuple[str, str]:
        if self.profile_panel.name_edit.isVisible():
            name = self.profile_panel.name_edit.text().strip()
            email = self.profile_panel.email_edit.text().strip()
            return name, email
        profile = self._profile_by_email(self.active_email)
        if profile:
            return profile.name, profile.email
        return "", ""

    def _resolve_data_dir(self) -> Optional[str]:
        if self.workflow_panel.demo_checkbox.isChecked():
            return str(FILES_DIR_DEMO)
        path = self.workflow_panel.path_edit.text().strip()
        if not path:
            return None
        return path

    def _on_generate(self) -> None:
        name, email = self._current_name_email()
        data_dir = self._resolve_data_dir()

        if not name:
            self._set_status("Nombre vacío", error=True)
            return
        if not EMAIL_RE.fullmatch(email):
            self._set_status("Email inválido", error=True)
            return
        if not data_dir:
            self._set_status("Carpeta de datos no seleccionada", error=True)
            return
        if not Path(data_dir).exists():
            self._set_status(f"Ruta no encontrada: {data_dir}", error=True)
            return

        self._set_status("Generando presentación...")
        self.workflow_panel.generate_button.setEnabled(False)
        self.workflow_panel.set_output_buttons_enabled(False)
        self.workflow_panel.append_log(f"Iniciando generación para {name}...")
        self._show_progress_dialog()

        worker = PresentationWorker(name, email, data_dir)
        worker.signals.log.connect(self._handle_log)
        worker.signals.finished.connect(self._generation_finished)
        self.thread_pool.start(worker)

    def _handle_log(self, message: str, level: str) -> None:
        self.workflow_panel.append_log(message, level)

    def _generation_finished(self, ok: bool, message: str, output_dir: object, ppt_path: object) -> None:
        self.workflow_panel.generate_button.setEnabled(True)
        self._hide_progress_dialog()

        if ok:
            self.output_dir = str(output_dir) if isinstance(output_dir, str) else None
            self.output_ppt = str(ppt_path) if isinstance(ppt_path, str) else None
            self.workflow_panel.set_output_buttons_enabled(self.output_dir is not None)
            self._finalize_profiles()
            self._set_status(message)
            if self.output_dir:
                self.workflow_panel.append_log(
                    f"Archivo disponible en {self.output_dir}",
                    level="success",
                )
        else:
            self.workflow_panel.append_log(message, level="error")
            self._set_status(message, error=True)

    def _finalize_profiles(self) -> None:
        name = self.profile_panel.name_edit.text().strip()
        email = self.profile_panel.email_edit.text().strip()
        if self.profile_panel.name_edit.isVisible():
            if self.edit_mode == "new":
                self.profiles.append(Profile(name, email, validated=True))
                self.active_email = email
            elif self.edit_mode == "edit":
                profile = self._profile_by_email(self.active_email)
                if profile:
                    profile.name = name
                    profile.email = email
                    profile.validated = True
                    self.active_email = email
        else:
            profile = self._profile_by_email(self.active_email)
            if profile:
                profile.validated = True

        self.edit_mode = None
        self._toggle_edit_form(False)
        save_config(self.active_email, self.profiles)
        self._refresh_profiles()

    def _on_open_folder(self) -> None:
        if not self.output_dir:
            return
        abrir_explorador(Path(self.output_dir))

    def _on_open_ppt(self) -> None:
        if not self.output_ppt:
            return
        abrir_explorador(Path(self.output_ppt))

    def _set_status(self, message: str, error: bool = False) -> None:
        bar = self.window.statusBar()
        bar.showMessage(message)
        if error:
            bar.setStyleSheet("color: #e74c3c;")
        elif "exitosamente" in message.lower():
            bar.setStyleSheet("color: #2ecc71;")
        else:
            bar.setStyleSheet("color: #d0d5df;")
        if error:
            self.workflow_panel.append_log(message, level="error")

    def _show_progress_dialog(self) -> None:
        if self.progress_dialog is None:
            self.progress_dialog = QProgressDialog(
                "Generando presentación...",
                None,
                0,
                0,
                self.window,
            )
            self.progress_dialog.setWindowTitle("Procesando")
            self.progress_dialog.setWindowModality(Qt.ApplicationModal)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setAutoClose(False)
            self.progress_dialog.setAutoReset(False)
        self.progress_dialog.show()
        self.progress_dialog.raise_()

    def _hide_progress_dialog(self) -> None:
        if self.progress_dialog:
            self.progress_dialog.reset()
            self.progress_dialog.hide()


def abrir_explorador(path: Path) -> None:
    if not path.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform.startswith("darwin"):
        os.system(f"open '{path}'")
    else:
        os.system(f"xdg-open '{path}'")

