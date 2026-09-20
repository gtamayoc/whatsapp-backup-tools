"""
High-performance virtualized console view for wab_gui.
Features circular buffer to prevent memory bloat and UI freezing during heavy log streaming.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QCheckBox, QFileDialog
)
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt

from wab_gui.theme import (
    COLOR_DANUBE_950, COLOR_DANUBE_50, COLOR_DANUBE_100,
    COLOR_DANUBE_300, COLOR_WARNING, COLOR_ERROR, COLOR_SUCCESS, COLOR_MUTED
)


class VirtualizedConsole(QWidget):
    """
    Console log viewer with circular buffer cap (prevents memory spikes).
    """

    def __init__(self, max_lines: int = 2500, parent=None):
        super().__init__(parent)
        self.max_lines = max_lines
        self.auto_scroll = True
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)

        self.title_label = QLabel("Consola de Operaciones")
        self.title_label.setObjectName("h2")
        toolbar.addWidget(self.title_label)

        toolbar.addStretch()

        self.autoscroll_cb = QCheckBox("Auto-scroll")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.toggled.connect(self._toggle_autoscroll)
        toolbar.addWidget(self.autoscroll_cb)

        self.btn_copy = QPushButton("Copiar")
        self.btn_copy.setToolTip("Copiar todo el contenido al portapapeles")
        self.btn_copy.clicked.connect(self._copy_all)
        toolbar.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setToolTip("Limpiar la pantalla de logs")
        self.btn_clear.clicked.connect(self.clear)
        toolbar.addWidget(self.btn_clear)

        self.btn_export = QPushButton("Exportar...")
        self.btn_export.setToolTip("Guardar logs en un archivo .log")
        self.btn_export.clicked.connect(self._export_logs)
        toolbar.addWidget(self.btn_export)

        layout.addLayout(toolbar)

        # Text edit console
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setMaximumBlockCount(self.max_lines)

        # Monospace font with high legibility
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)

        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLOR_DANUBE_950};
                color: {COLOR_DANUBE_100};
                border: 1px solid #082945;
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.editor)

    def _toggle_autoscroll(self, checked: bool):
        self.auto_scroll = checked

    def append_log(self, text: str, level: str = "INFO"):
        """
        Append a log line with syntax coloring based on level.
        """
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        level_upper = level.upper()

        if "ERROR" in level_upper or "EXCEPTION" in level_upper:
            fmt.setForeground(QColor(COLOR_ERROR))
        elif "WARN" in level_upper:
            fmt.setForeground(QColor(COLOR_WARNING))
        elif "SUCCESS" in level_upper or "COMPLETE" in level_upper:
            fmt.setForeground(QColor(COLOR_SUCCESS))
        elif "DEBUG" in level_upper:
            fmt.setForeground(QColor(COLOR_MUTED))
        else:
            fmt.setForeground(QColor(COLOR_DANUBE_100))

        cursor.insertText(text.rstrip() + "\n", fmt)

        if self.auto_scroll:
            self.editor.moveCursor(QTextCursor.MoveOperation.End)

    def clear(self):
        self.editor.clear()

    def _copy_all(self):
        self.editor.selectAll()
        self.editor.copy()
        cursor = self.editor.textCursor()
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)

    def _export_logs(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Logs", "operacion_wab.log", "Archivos de Log (*.log);;Texto (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
