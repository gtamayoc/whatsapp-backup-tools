"""
Execution monitor tab with live progress bar, virtualized circular-buffer console,
and post-execution quick actions (open folder, reports, and launch web viewer).
"""

import os
import sys
import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal

from wab_gui.ui.components.console_view import VirtualizedConsole
from wab_gui.theme import (
    COLOR_DANUBE_50, COLOR_DANUBE_100, COLOR_DANUBE_200,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_DANUBE_800
)


class TabExecution(QWidget):
    """Real-time console, progress indicator, and results panel."""

    cancel_requested = Signal()
    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_dir: str = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 1. Status & Progress Card
        card_progress = QFrame()
        card_progress.setObjectName("card")
        lo_prog = QVBoxLayout(card_progress)
        lo_prog.setSpacing(6)

        header_prog = QHBoxLayout()
        self.lbl_status = QLabel("Listo para ejecutar")
        self.lbl_status.setObjectName("h2")
        header_prog.addWidget(self.lbl_status)

        header_prog.addStretch()

        self.lbl_counter = QLabel("0 / 0")
        self.lbl_counter.setStyleSheet(f"color: {COLOR_DANUBE_200}; font-weight: 500;")
        header_prog.addWidget(self.lbl_counter)
        lo_prog.addLayout(header_prog)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        lo_prog.addWidget(self.progress_bar)

        layout.addWidget(card_progress)

        # 2. Virtualized Console (circular buffer)
        self.console = VirtualizedConsole(max_lines=3000)
        layout.addWidget(self.console)

        # 3. Post-execution Actions Bar
        self.card_actions = QFrame()
        self.card_actions.setObjectName("card")
        lo_actions = QHBoxLayout(self.card_actions)
        lo_actions.setSpacing(8)

        self.btn_open_folder = QPushButton("Abrir Carpeta")
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        lo_actions.addWidget(self.btn_open_folder)

        self.btn_open_missing = QPushButton("Reporte Faltantes")
        self.btn_open_missing.clicked.connect(self._open_missing_report)
        lo_actions.addWidget(self.btn_open_missing)

        self.btn_open_duplicates = QPushButton("Reporte Duplicados")
        self.btn_open_duplicates.clicked.connect(self._open_duplicates_report)
        lo_actions.addWidget(self.btn_open_duplicates)

        lo_actions.addStretch()

        self.btn_launch_viewer = QPushButton("🌐 Abrir en Visor Web")
        self.btn_launch_viewer.setStyleSheet(f"background-color: {COLOR_SUCCESS}; color: #010b18; font-weight: bold;")
        self.btn_launch_viewer.clicked.connect(self._launch_web_viewer)
        lo_actions.addWidget(self.btn_launch_viewer)

        layout.addWidget(self.card_actions)

    def set_output_dir(self, path: str):
        self.output_dir = path

    def set_running(self, running: bool):
        if running:
            self.lbl_status.setText("Ejecutando proceso...")
            self.progress_bar.setValue(0)
            self.card_actions.setEnabled(False)
        else:
            self.card_actions.setEnabled(True)

    def update_progress(self, current: int, total: int, phase: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_counter.setText(f"{current} / {total} ({pct}%)")
        self.lbl_status.setText(phase)

    def on_finished(self, return_code: int):
        self.set_running(False)
        if return_code == 0:
            self.lbl_status.setText("✓ Operación completada con éxito")
            self.lbl_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")
            self.progress_bar.setValue(100)
        else:
            self.lbl_status.setText(f"⚠️ Proceso finalizado con código {return_code}")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ERROR}; font-weight: bold;")

    def _open_file_or_dir(self, target_path: str):
        if not target_path or not os.path.exists(target_path):
            self.console.append_log(f"Ruta no encontrada: {target_path}", "WARNING")
            return
        try:
            if sys.platform == "win32":
                os.startfile(target_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", target_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", target_path])
        except Exception as e:
            self.console.append_log(f"Error al abrir {target_path}: {e}", "ERROR")

    def _open_output_folder(self):
        self._open_file_or_dir(self.output_dir)

    def _open_missing_report(self):
        report = os.path.join(self.output_dir, "missing_media_report.csv")
        self._open_file_or_dir(report)

    def _open_duplicates_report(self):
        report = os.path.join(self.output_dir, "duplicate_media_report.csv")
        self._open_file_or_dir(report)

    def _launch_web_viewer(self):
        if not self.output_dir or not os.path.exists(self.output_dir):
            self.console.append_log("Debe especificar una carpeta de salida válida con archivo existente.", "WARNING")
            return

        db_path = os.path.join(self.output_dir, ".wa_media_archiver.db")
        if not os.path.exists(db_path):
            self.console.append_log("No se encontró .wa_media_archiver.db en la carpeta indicada.", "WARNING")
            return

        import subprocess
        cmd = [sys.executable, "-m", "wab_viewer", self.output_dir]
        try:
            subprocess.Popen(cmd)
            self.console.append_log("Iniciando Visor Web de Chats (wab_viewer)...", "SUCCESS")
        except Exception as e:
            self.console.append_log(f"Error al lanzar wab_viewer: {e}", "ERROR")
