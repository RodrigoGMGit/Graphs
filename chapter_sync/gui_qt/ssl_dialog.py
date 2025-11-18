"""Diálogos para diagnóstico y configuración SSL."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QCheckBox
)

from chapter_sync.ssl_diagnostics import (
    run_diagnostic,
    generate_report,
    SystemDiagnosticResult,
)
from chapter_sync.ssl_config import set_ssl_verify


class DiagnosticWorker(QThread):
    """Worker thread para ejecutar diagnóstico sin bloquear UI."""
    finished = Signal(SystemDiagnosticResult)
    
    def run(self):
        result = run_diagnostic()
        self.finished.emit(result)


class SSLDiagnosticDialog(QDialog):
    """Ventana de diagnóstico del sistema."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnóstico del Sistema")
        self.setMinimumSize(800, 600)
        self.result: SystemDiagnosticResult | None = None
        self._build_ui()
        self._run_diagnostic()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Título
        title = QLabel("Diagnóstico del Sistema")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Descripción
        desc = QLabel(
            "Este diagnóstico verificará los permisos de escritura y la "
            "conectividad de red necesarios para que la aplicación funcione correctamente."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Área de reporte
        report_label = QLabel("Reporte de diagnóstico:")
        layout.addWidget(report_label)
        
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlaceholderText("Ejecutando diagnóstico...")
        self.report_text.setStyleSheet(
            "QTextEdit { background-color: #1e1f24; color: #d0d5df; font-family: 'Consolas', 'Courier New', monospace; }"
        )
        layout.addWidget(self.report_text)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Guardar reporte")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_report)
        button_layout.addWidget(self.save_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("Cerrar")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _run_diagnostic(self):
        """Ejecuta el diagnóstico en un thread separado."""
        self.worker = DiagnosticWorker()
        self.worker.finished.connect(self._on_diagnostic_finished)
        self.worker.start()
    
    def _on_diagnostic_finished(self, result: SystemDiagnosticResult):
        """Se llama cuando el diagnóstico termina."""
        self.result = result
        report_text = generate_report(result)
        
        # Agregar información adicional del error si está disponible
        if result.has_ssl_error and result.ssl_error_traceback:
            report_text += "\n\n" + "="*70 + "\n"
            report_text += "  TRACEBACK COMPLETO DEL ERROR\n"
            report_text += "="*70 + "\n\n"
            report_text += result.ssl_error_traceback
        
        self.report_text.setPlainText(report_text)
        self.report_text.moveCursor(self.report_text.textCursor().End)
        self.save_button.setEnabled(True)
    
    def _get_outputs_dir(self) -> Path:
        """Obtiene el directorio de outputs, manejando ejecutable y script."""
        if getattr(sys, "frozen", False):
            exec_dir = Path(sys.executable).resolve().parent
            return exec_dir / "outputs"
        else:
            # Running as script
            workspace_root = Path(__file__).resolve().parent.parent.parent
            return workspace_root / "chapter_sync" / "outputs"
    
    def _save_report(self):
        """Guarda el reporte automáticamente en un subdirectorio de outputs."""
        if not self.result:
            return
        
        try:
            # Obtener directorio de outputs
            outputs_dir = self._get_outputs_dir()
            
            # Crear subdirectorio para diagnósticos
            diagnostic_dir = outputs_dir / "diagnosticos"
            diagnostic_dir.mkdir(parents=True, exist_ok=True)
            
            # Generar nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"diagnostico_{timestamp}.txt"
            file_path = diagnostic_dir / filename
            
            # Generar reporte completo
            report_text = generate_report(self.result)
            if self.result.has_ssl_error and self.result.ssl_error_traceback:
                report_text += "\n\n" + "="*70 + "\n"
                report_text += "  TRACEBACK COMPLETO DEL ERROR\n"
                report_text += "="*70 + "\n\n"
                report_text += self.result.ssl_error_traceback
            
            # Guardar archivo
            file_path.write_text(report_text, encoding='utf-8')
            
            QMessageBox.information(
                self,
                "Reporte guardado",
                f"El reporte se ha guardado en:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo guardar el reporte:\n{e}"
            )


class SSLConfigDialog(QDialog):
    """Diálogo para configurar SSL cuando se detecta un error."""
    
    def __init__(self, error_message: str = "", error_traceback: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error de Verificación SSL Detectado")
        self.setMinimumSize(700, 500)
        self.error_message = error_message
        self.error_traceback = error_traceback
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Título
        title = QLabel("Error de Verificación SSL Detectado")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Mensaje explicativo
        explanation = QLabel(
            "Se detectó un error al verificar el certificado SSL. Esto generalmente ocurre "
            "en entornos corporativos donde un proxy o firewall intercepta las conexiones SSL.\n\n"
            "Opciones:\n"
            "• Obtener el certificado raíz de la CA corporativa del equipo de TI y colocarlo "
            "en el directorio de la aplicación (recomendado)\n"
            "• Desactivar temporalmente la verificación SSL (menos seguro)"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        
        # Área de error
        error_label = QLabel("Detalle del error:")
        error_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(error_label)
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(200)
        self.error_text.setStyleSheet(
            "QTextEdit { background-color: #2d2d2d; color: #ff6b6b; font-family: 'Consolas', 'Courier New', monospace; }"
        )
        
        # Construir texto del error
        error_display = ""
        if self.error_message:
            error_display += f"Mensaje de error:\n{self.error_message}\n\n"
        if self.error_traceback:
            error_display += "Traceback completo:\n"
            error_display += "-" * 70 + "\n"
            error_display += self.error_traceback
        else:
            error_display += "(No hay traceback disponible)"
        
        self.error_text.setPlainText(error_display)
        layout.addWidget(self.error_text)
        
        # Advertencia de seguridad
        warning = QLabel(
            "⚠️ ADVERTENCIA: Desactivar la verificación SSL reduce la seguridad de las conexiones. "
            "Solo use esta opción en entornos corporativos controlados."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #f1c40f; font-weight: bold;")
        layout.addWidget(warning)
        
        # Checkbox para desactivar SSL
        self.disable_ssl_checkbox = QCheckBox(
            "Desactivar verificación SSL (menos seguro)"
        )
        layout.addWidget(self.disable_ssl_checkbox)
        
        # Botones
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        apply_button = QPushButton("Aplicar")
        apply_button.clicked.connect(self._apply_config)
        button_layout.addWidget(apply_button)
        
        layout.addLayout(button_layout)
    
    def _apply_config(self):
        """Aplica la configuración SSL seleccionada."""
        if self.disable_ssl_checkbox.isChecked():
            # Mostrar confirmación adicional
            reply = QMessageBox.warning(
                self,
                "Confirmar desactivación SSL",
                "¿Está seguro de que desea desactivar la verificación SSL?\n\n"
                "Esto hará que la aplicación sea vulnerable a ataques Man-in-the-Middle.\n"
                "Solo debe hacer esto en entornos corporativos controlados.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                set_ssl_verify(False)
                QMessageBox.information(
                    self,
                    "Configuración aplicada",
                    "La verificación SSL ha sido desactivada.\n"
                    "La aplicación se conectará sin verificar certificados."
                )
                self.accept()
        else:
            QMessageBox.information(
                self,
                "Información",
                "No se realizaron cambios en la configuración SSL.\n\n"
                "Para resolver el problema, contacte al equipo de TI para obtener "
                "el certificado raíz de la CA corporativa."
            )
            self.reject()

