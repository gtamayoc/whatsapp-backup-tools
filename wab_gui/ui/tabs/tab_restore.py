"""
Restore tab for reconstructing original WhatsApp Media tree from an archive (Android).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
    QCheckBox, QPushButton
)

from wab_gui.ui.components.path_picker import PathPicker
from wab_gui.theme import COLOR_DANUBE_200, COLOR_WARNING


class TabRestore(QWidget):
    """Configuration panel for the restore subcommand."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("card")
        card_lo = QVBoxLayout(card)
        card_lo.setSpacing(10)

        title = QLabel("Restauración de Copia de Seguridad (Android)")
        title.setObjectName("h2")
        card_lo.addWidget(title)

        desc = QLabel(
            "Reconstruye la estructura original de carpetas de WhatsApp (Media/WhatsApp Audio, Media/WhatsApp Images, etc.) "
            "a partir de un archivo previamente procesado. Solo compatible con archivos originados en Android."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLOR_DANUBE_200}; font-size: 12px;")
        card_lo.addWidget(desc)

        card_lo.addWidget(QLabel("Ruta del Archivo a Restaurar (-o / --output):"))
        self.picker_output = PathPicker(
            placeholder="Seleccione la carpeta raíz del archivo previamente creado...",
            mode="dir",
            tooltip="Carpeta que contiene la base de datos .wa_media_archiver.db.\nEquivalente CLI: -o / --output"
        )
        card_lo.addWidget(self.picker_output)

        self.cb_dry_run = QCheckBox("Modo Simulación (--dry-run) — Comprobar sin restaurar archivos")
        self.cb_dry_run.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: 500;")
        card_lo.addWidget(self.cb_dry_run)

        layout.addWidget(card)
        layout.addStretch()

    def get_cli_args(self) -> list[str]:
        args = ["-m", "wab_archiver", "restore"]
        out = self.picker_output.get_path()
        if out:
            args.extend(["-o", out])
        if self.cb_dry_run.isChecked():
            args.append("--dry-run")
        return args
