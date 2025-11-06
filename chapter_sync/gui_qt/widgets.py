"""Qt widget hierarchy for the ChapterSync GUI variant."""

from __future__ import annotations

from datetime import datetime
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)


class MainWindow(QMainWindow):
    """Main application window for the PySide6 GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ChapterSync")
        self.resize(1120, 760)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("ChapterSync")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Generación de Presentaciones")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root_layout.addLayout(header_layout)

        # Splitter content
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.profile_panel = ProfilePanel()
        self.workflow_panel = WorkflowPanel()
        splitter.addWidget(self.profile_panel)
        splitter.addWidget(self.workflow_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 760])
        root_layout.addWidget(splitter)

        # Status bar placeholder
        self._status_bar = self.statusBar()
        self._status_bar.showMessage("Listo")


class ProfilePanel(QFrame):
    """Left-hand panel that manages stored profiles."""

    profile_selected = Signal(str)
    create_requested = Signal()
    edit_requested = Signal()
    delete_requested = Signal()
    cancel_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("profilePanel")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(280)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QLabel("Perfiles de Chapter Leader")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        hint = QLabel("Selecciona un perfil guardado o crea uno nuevo.")
        hint.setWordWrap(True)
        hint.setObjectName("profileHint")
        layout.addWidget(hint)

        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("profileCombo")
        self.profile_combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self.profile_combo)

        button_row = QHBoxLayout()
        self.new_button = QPushButton("Nuevo")
        self.new_button.clicked.connect(self.create_requested)
        self.edit_button = QPushButton("Editar")
        self.edit_button.clicked.connect(self.edit_requested)
        self.delete_button = QPushButton("Eliminar")
        self.delete_button.clicked.connect(self.delete_requested)
        button_row.addWidget(self.new_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.delete_button)
        layout.addLayout(button_row)

        # Hidden form for create/edit – will be toggled later by controllers
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del Chapter Leader")
        self.name_edit.hide()

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Correo del Chapter Leader")
        self.email_edit.hide()

        self.info_label = QLabel(
            "Los cambios se guardarán al generar una presentación exitosa."
        )
        self.info_label.setWordWrap(True)
        self.info_label.hide()

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.cancel_button.hide()

        layout.addWidget(self.name_edit)
        layout.addWidget(self.email_edit)
        layout.addWidget(self.info_label)
        layout.addWidget(self.cancel_button)
        layout.addStretch(1)

    def _on_combo_changed(self, value: str) -> None:
        if value:
            self.profile_selected.emit(value)


class WorkflowPanel(QFrame):
    """Right-hand panel with action controls."""

    generate_requested = Signal()
    open_folder_requested = Signal()
    open_ppt_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("workflowPanel")
        self.setFrameShape(QFrame.StyledPanel)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(18)

        layout.addWidget(self._build_actions_group())
        layout.addWidget(self._build_log_group(), stretch=1)

    def _build_actions_group(self) -> QGroupBox:
        group = QGroupBox("Acciones")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)

        self.generate_button = QPushButton("Generar presentación")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setMinimumHeight(50)
        self.generate_button.clicked.connect(self.generate_requested)

        self.open_folder_button = QPushButton("Abrir carpeta de salida")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.setMinimumHeight(50)
        self.open_folder_button.clicked.connect(self.open_folder_requested)

        self.open_ppt_button = QPushButton("Abrir presentación más reciente")
        self.open_ppt_button.setEnabled(False)
        self.open_ppt_button.setMinimumHeight(50)
        self.open_ppt_button.clicked.connect(self.open_ppt_requested)

        group_layout.addWidget(self.generate_button)
        group_layout.addWidget(self.open_folder_button)
        group_layout.addWidget(self.open_ppt_button)
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Registro de actividad")
        group_layout = QVBoxLayout(group)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        self.log_view.setPlaceholderText("Los mensajes del proceso aparecerán aquí.")
        self.log_view.setStyleSheet(
            "QTextEdit { background-color: #1e1f24; color: #d0d5df; }"
        )
        self._log_rows = 0

        group_layout.addWidget(self.log_view)
        return group

    # Helper methods that the controller will use in next phases -----------------
    def append_log(self, message: str, level: str = "info") -> None:
        colors = {
            "error": "#e74c3c",
            "warn": "#f1c40f",
            "success": "#2ecc71",
            "info": "#8fb3ff",
        }
        color = colors.get(level, colors["info"])
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_message = escape(message)
        html = f"<span style='color:#6c7a89'>[{timestamp}]</span> <span style='color:{color}'>{safe_message}</span>"
        self.log_view.append(html)
        self._log_rows += 1
        if self._log_rows > 500:
            self.log_view.clear()
            self._log_rows = 0

    def clear_logs(self) -> None:
        self.log_view.clear()
        self._log_rows = 0

    def set_output_buttons_enabled(self, enabled: bool) -> None:
        self.open_folder_button.setEnabled(enabled)
        self.open_ppt_button.setEnabled(enabled)
