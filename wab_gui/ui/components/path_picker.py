"""
Custom reusable path picker widget with file/folder dialog, validation indicator, tooltip,
and optional MRU history menu (up to 20 recent paths).
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QLabel, QMenu
)
from PySide6.QtCore import Signal

from wab_gui.services.history_service import HistoryService
from wab_gui.theme import (
    COLOR_MUTED, COLOR_SUCCESS, COLOR_WARNING, COLOR_BLACK_700,
    COLOR_BLACK_800, COLOR_BLACK_900, COLOR_BLACK_50
)


class PathPicker(QWidget):
    """Clean input with Browse button, history menu, tooltip info, and presence indicator."""

    path_changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "",
        mode: str = "dir",  # 'dir', 'file_open', 'file_save'
        file_filter: str = "Todos los archivos (*.*)",
        tooltip: str = "",
        history_key: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.file_filter = file_filter
        self.history_key = history_key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        if tooltip:
            self.input.setToolTip(tooltip)
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        # History dropdown button (if enabled)
        if self.history_key:
            self.btn_history = QPushButton("🕒")
            self.btn_history.setToolTip("Rutas recientes (últimas 20)")
            self.btn_history.setFixedWidth(32)
            self.btn_history.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_BLACK_900};
                    border: 1px solid {COLOR_BLACK_700};
                    border-radius: 6px;
                    padding: 4px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_BLACK_800};
                    border-color: {COLOR_BLACK_50};
                }}
            """)
            self.btn_history.clicked.connect(self._show_history_menu)
            layout.addWidget(self.btn_history)

        self.btn_browse = QPushButton("Explorar...")
        if tooltip:
            self.btn_browse.setToolTip(tooltip)
        self.btn_browse.clicked.connect(self._open_dialog)
        layout.addWidget(self.btn_browse)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 10px;")
        layout.addWidget(self.status_dot)

    def _show_history_menu(self):
        if not self.history_key:
            return

        menu = QMenu(self)
        history = HistoryService.get_history(self.history_key)

        if not history:
            action_empty = menu.addAction("(Sin rutas recientes)")
            action_empty.setEnabled(False)
        else:
            for path_entry in history:
                # Truncate display if very long but show full path in tooltip
                display_text = path_entry if len(path_entry) <= 55 else f"...{path_entry[-52:]}"
                action = menu.addAction(f"📁 {display_text}")
                action.setToolTip(path_entry)
                # Capture current path in closure
                action.triggered.connect(lambda checked=False, p=path_entry: self._select_history_path(p))

            menu.addSeparator()
            action_clear = menu.addAction("🗑️ Borrar historial")
            action_clear.triggered.connect(lambda: HistoryService.clear_history(self.history_key))

        # Show menu below the history button
        menu.exec(self.btn_history.mapToGlobal(self.btn_history.rect().bottomLeft()))

    def _select_history_path(self, path: str):
        self.input.setText(path)
        if self.history_key:
            HistoryService.add_path(path, self.history_key)

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
            if self.history_key:
                HistoryService.add_path(norm, self.history_key)

    def _on_text_changed(self, text: str):
        val = text.strip()
        if not val:
            self.status_dot.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 10px;")
            self.status_dot.setToolTip("Campo vacío")
        elif Path(val).exists():
            self.status_dot.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 10px;")
            self.status_dot.setToolTip("Ruta verificada en el disco")
            if self.history_key:
                HistoryService.add_path(val, self.history_key)
        else:
            self.status_dot.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 10px;")
            self.status_dot.setToolTip("Ruta no encontrada localmente")
        self.path_changed.emit(val)

    def get_path(self) -> str:
        return self.input.text().strip()

    def set_path(self, path: str):
        self.input.setText(path)
