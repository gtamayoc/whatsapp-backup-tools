"""
Custom reusable path picker widget with file/folder dialog, validation indicator and tooltip.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QLabel
)
from PySide6.QtCore import Signal
from pathlib import Path

from wab_gui.theme import COLOR_MUTED, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANUBE_800


class PathPicker(QWidget):
    """Clean input with Browse button, tooltip info, and presence indicator."""

    path_changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "",
        mode: str = "dir",  # 'dir', 'file_open', 'file_save'
        file_filter: str = "Todos los archivos (*.*)",
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.file_filter = file_filter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        if tooltip:
            self.input.setToolTip(tooltip)
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        self.btn_browse = QPushButton("Explorar...")
        if tooltip:
            self.btn_browse.setToolTip(tooltip)
        self.btn_browse.clicked.connect(self._open_dialog)
        layout.addWidget(self.btn_browse)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 10px;")
        layout.addWidget(self.status_dot)

    def _open_dialog(self):
        current = self.input.text().strip()
        start_dir = current if current and Path(current).exists() else ""

        if self.mode == "dir":
            selected = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta", start_dir)
        elif self.mode == "file_save":
            selected, _ = QFileDialog.getSaveFileName(self, "Guardar Archivo", start_dir, self.file_filter)
        else:
            selected, _ = QFileDialog.getOpenFileName(self, "Seleccionar Archivo", start_dir, self.file_filter)

        if selected:
            # Normalize to forward slash
            norm = selected.replace("\\", "/")
            self.input.setText(norm)

    def _on_text_changed(self, text: str):
        val = text.strip()
        if not val:
            self.status_dot.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 10px;")
            self.status_dot.setToolTip("Campo vacío")
        elif Path(val).exists():
            self.status_dot.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 10px;")
            self.status_dot.setToolTip("Ruta verificada en el disco")
        else:
            self.status_dot.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 10px;")
            self.status_dot.setToolTip("Ruta no encontrada localmente")
        self.path_changed.emit(val)

    def get_path(self) -> str:
        return self.input.text().strip()

    def set_path(self, path: str):
        self.input.setText(path)
