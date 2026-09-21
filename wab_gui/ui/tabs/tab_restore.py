"""
Restore and Device Free-Space tab for WhatsApp Backup Tools.
Presents two clear, safe operations:
1. Restaurar WhatsApp (PC -> Celular o Carpeta Local)
2. Liberar Espacio en Celular (purge-device vía ADB tras verificación)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QCheckBox, QStackedWidget, QMessageBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal

from wab_gui.ui.components.path_picker import PathPicker
from wab_gui.theme import (
    COLOR_BLACK_50, COLOR_BLACK_100, COLOR_BLACK_200, COLOR_BLACK_400,
    COLOR_BLACK_700, COLOR_BLACK_800, COLOR_BLACK_900, COLOR_BLACK_950,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_MUTED, COLOR_SURFACE
)


class TabRestore(QWidget):
    """Panel for restoring WhatsApp data and freeing device space safely."""

    request_execution = Signal(list, str)  # (cli_args, output_dir)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "restore"
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # 1. Top Segmented Switcher (Restaurar vs Liberar Celular)
        switcher_frame = QFrame()
        switcher_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BLACK_900};
                border-radius: 8px;
                border: 1px solid {COLOR_BLACK_800};
            }}
        """)
        switcher_layout = QHBoxLayout(switcher_frame)
        switcher_layout.setContentsMargins(4, 4, 4, 4)
        switcher_layout.setSpacing(6)

        self.btn_tab_restore = QPushButton("🔄  Restaurar WhatsApp")
        self.btn_tab_restore.clicked.connect(lambda: self._set_mode("restore"))
        switcher_layout.addWidget(self.btn_tab_restore, 1)

        self.btn_tab_purge = QPushButton("📱  Liberar Espacio en Celular")
        self.btn_tab_purge.clicked.connect(lambda: self._set_mode("purge"))
        switcher_layout.addWidget(self.btn_tab_purge, 1)

        main_layout.addWidget(switcher_frame)

        # 2. Stacked Pages for each mode
        self.stack = QStackedWidget()

        # --- Page 0: RESTAURAR ---
        page_restore = QWidget()
        lo_res = QVBoxLayout(page_restore)
        lo_res.setContentsMargins(0, 4, 0, 0)
        lo_res.setSpacing(12)

        card_res = QFrame()
        card_res.setObjectName("card")
        lo_card_res = QVBoxLayout(card_res)
        lo_card_res.setSpacing(12)

        lbl_res_title = QLabel("Restaurar WhatsApp desde la Copia")
        lbl_res_title.setObjectName("h2")
        lo_card_res.addWidget(lbl_res_title)

        lbl_res_desc = QLabel(
            "Reconstruye la estructura nativa de WhatsApp (fotos, videos, audios y chats) "
            "para que la aplicación vuelva a ver tus archivos como antes."
        )
        lbl_res_desc.setStyleSheet(f"color: {COLOR_BLACK_400}; font-size: 12px;")
        lbl_res_desc.setWordWrap(True)
        lo_card_res.addWidget(lbl_res_desc)

        lo_card_res.addWidget(QLabel("Carpeta de la Copia de Seguridad en tu PC:"))
        self.picker_restore_output = PathPicker(
            placeholder="Selecciona la carpeta donde guardaste tu copia...",
            mode="dir",
            tooltip="Carpeta del archivo que contiene .wa_media_archiver.db.",
            history_key="output_dir"
        )
        lo_card_res.addWidget(self.picker_restore_output)

        # Destination selection: Celular vs Carpeta
        lo_card_res.addWidget(QLabel("Destino de la Restauración:"))
        dest_group_frame = QFrame()
        lo_dest = QVBoxLayout(dest_group_frame)
        lo_dest.setContentsMargins(8, 6, 8, 6)
        lo_dest.setSpacing(6)

        self.rb_dest_device = QRadioButton("📱  Directamente al Teléfono Celular (vía ADB)")
        self.rb_dest_device.setChecked(True)
        self.rb_dest_device.setToolTip("Restaura a /Android/media/com.whatsapp/WhatsApp/Media y actualiza la galería.")
        lo_dest.addWidget(self.rb_dest_device)

        self.rb_dest_local = QRadioButton("📁  Reconstruir en una carpeta en el PC")
        self.rb_dest_local.setToolTip("Crea la estructura original Media/ en una carpeta local.")
        lo_dest.addWidget(self.rb_dest_local)

        self.picker_restore_local_dest = PathPicker(
            placeholder="Carpeta de destino personalizada (opcional)...",
            mode="dir",
            tooltip="Si se deja vacío, se reconstruye dentro de la carpeta de la copia.",
            history_key="output_dir"
        )
        self.picker_restore_local_dest.setEnabled(False)
        lo_dest.addWidget(self.picker_restore_local_dest)

        self.rb_dest_local.toggled.connect(self.picker_restore_local_dest.setEnabled)
        lo_card_res.addWidget(dest_group_frame)

        # Options
        self.cb_restore_include_db = QCheckBox("Incluir Base de Datos cifrada (msgstore.db.cryptXX)")
        self.cb_restore_include_db.setChecked(True)
        self.cb_restore_include_db.setToolTip("Restaura la base de datos a Databases/ para que WhatsApp la detecte al reinstalar.")
        lo_card_res.addWidget(self.cb_restore_include_db)

        self.cb_restore_dry_run = QCheckBox("Solo simular (probar sin escribir en el dispositivo o disco)")
        self.cb_restore_dry_run.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 12px;")
        lo_card_res.addWidget(self.cb_restore_dry_run)

        btn_run_res = QPushButton("🔄  Restaurar WhatsApp Ahora")
        btn_run_res.setObjectName("primaryBtn")
        btn_run_res.clicked.connect(self._on_run_restore_clicked)
        lo_card_res.addWidget(btn_run_res)

        lo_res.addWidget(card_res)
        lo_res.addStretch()
        self.stack.addWidget(page_restore)

        # --- Page 1: LIBERAR ESPACIO EN CELULAR ---
        page_purge = QWidget()
        lo_purge = QVBoxLayout(page_purge)
        lo_purge.setContentsMargins(0, 4, 0, 0)
        lo_purge.setSpacing(12)

        card_purge = QFrame()
        card_purge.setObjectName("card")
        lo_card_purge = QVBoxLayout(card_purge)
        lo_card_purge.setSpacing(12)

        lbl_purge_title = QLabel("Liberar Espacio en el Teléfono Móvil")
        lbl_purge_title.setObjectName("h2")
        lo_card_purge.addWidget(lbl_purge_title)

        lbl_purge_desc = QLabel(
            "Elimina del teléfono celular únicamente las fotos, videos y audios que ya están 100% respaldados "
            "y verificados en tu PC para recuperar gigabytes de almacenamiento en el móvil.\n\n"
            "🛡️ Máxima Seguridad Garantizada:\n"
            "• Se ejecuta una auditoría criptográfica previa obligatoria de la copia.\n"
            "• Las bases de datos de mensajes (msgstore*), claves y copias de seguridad del celular NUNCA se tocan.\n"
            "• La copia de seguridad en tu PC se conserva COMPLETAMENTE INTACTA."
        )
        lbl_purge_desc.setStyleSheet(f"color: {COLOR_BLACK_400}; font-size: 12px;")
        lbl_purge_desc.setWordWrap(True)
        lo_card_purge.addWidget(lbl_purge_desc)

        lo_card_purge.addWidget(QLabel("Carpeta de tu Copia de Seguridad en el PC:"))
        self.picker_purge_output = PathPicker(
            placeholder="Selecciona la carpeta donde guardaste tu copia en PC...",
            mode="dir",
            tooltip="Carpeta que contiene la copia que será contrastada contra el teléfono.",
            history_key="output_dir"
        )
        lo_card_purge.addWidget(self.picker_purge_output)

        self.cb_purge_dry_run = QCheckBox("Solo simular (calcular GB y archivos a liberar sin borrar nada)")
        self.cb_purge_dry_run.setChecked(True)
        self.cb_purge_dry_run.setStyleSheet(f"color: {COLOR_WARNING}; font-weight: 500;")
        lo_card_purge.addWidget(self.cb_purge_dry_run)

        btn_box = QHBoxLayout()
        btn_verify = QPushButton("🔍  1. Verificar Copia en PC")
        btn_verify.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BLACK_900};
                color: {COLOR_BLACK_100};
                border: 1px solid {COLOR_BLACK_700};
                border-radius: 8px;
                padding: 10px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BLACK_800};
            }}
        """)
        btn_verify.clicked.connect(self._on_run_verify_clicked)
        btn_box.addWidget(btn_verify)

        btn_run_purge = QPushButton("📱  2. Liberar Espacio en Celular")
        btn_run_purge.setObjectName("primaryBtn")
        btn_run_purge.clicked.connect(self._on_run_purge_clicked)
        btn_box.addWidget(btn_run_purge, 1)

        lo_card_purge.addLayout(btn_box)

        lo_purge.addWidget(card_purge)
        lo_purge.addStretch()
        self.stack.addWidget(page_purge)

        main_layout.addWidget(self.stack)

        # Apply initial styles
        self._set_mode("restore")

    def _set_mode(self, mode: str):
        self._mode = mode
        active_style = f"""
            QPushButton {{
                background-color: {COLOR_BLACK_50};
                color: {COLOR_BLACK_950};
                font-weight: 600;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                border: none;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_BLACK_400};
                font-weight: 500;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                border: none;
            }}
            QPushButton:hover {{
                color: {COLOR_BLACK_100};
                background-color: {COLOR_BLACK_800};
            }}
        """

        if mode == "restore":
            self.btn_tab_restore.setStyleSheet(active_style)
            self.btn_tab_purge.setStyleSheet(inactive_style)
            self.stack.setCurrentIndex(0)
        else:
            self.btn_tab_restore.setStyleSheet(inactive_style)
            self.btn_tab_purge.setStyleSheet(active_style)
            self.stack.setCurrentIndex(1)

    def set_default_output(self, path: str):
        """Sync output path when changed globally."""
        if path:
            self.picker_restore_output.set_path(path)
            self.picker_purge_output.set_path(path)

    def get_output_dir(self) -> str:
        if self._mode == "restore":
            return self.picker_restore_output.get_path()
        return self.picker_purge_output.get_path()

    def get_cli_args(self) -> list[str]:
        if self._mode == "restore":
            out = self.picker_restore_output.get_path()
            args = ["-m", "wab_archiver", "restore"]
            if out:
                args.extend(["-o", out])
            if self.rb_dest_device.isChecked():
                args.append("--to-device")
            elif self.rb_dest_local.isChecked():
                custom_dest = self.picker_restore_local_dest.get_path()
                if custom_dest:
                    args.extend(["--to-dir", custom_dest])
            if self.cb_restore_include_db.isChecked():
                args.append("--include-db")
            if self.cb_restore_dry_run.isChecked():
                args.append("--dry-run")
            return args
        else:
            out = self.picker_purge_output.get_path()
            args = ["-m", "wab_archiver", "purge-device"]
            if out:
                args.extend(["-o", out])
            if self.cb_purge_dry_run.isChecked():
                args.append("--dry-run")
            args.append("-y")
            return args

    def _on_run_restore_clicked(self):
        out = self.picker_restore_output.get_path()
        if not out:
            QMessageBox.warning(self, "Campo Requerido", "Por favor selecciona la carpeta donde está tu copia de seguridad.")
            return
        args = self.get_cli_args()
        self.request_execution.emit(args, out)

    def _on_run_verify_clicked(self):
        out = self.picker_purge_output.get_path()
        if not out:
            QMessageBox.warning(self, "Campo Requerido", "Por favor selecciona la carpeta de tu copia de seguridad.")
            return
        args = ["-m", "wab_archiver", "verify", "-o", out]
        self.request_execution.emit(args, out)

    def _on_run_purge_clicked(self):
        out = self.picker_purge_output.get_path()
        if not out:
            QMessageBox.warning(self, "Campo Requerido", "Por favor selecciona la carpeta de tu copia de seguridad.")
            return

        if not self.cb_purge_dry_run.isChecked():
            confirm = QMessageBox.question(
                self,
                "Liberar Almacenamiento en Celular",
                "Se eliminarán de tu teléfono celular las fotos, videos y audios que ya están 100% verificados y respaldados en este PC.\n\n"
                "Tus mensajes de WhatsApp y la copia en tu PC permanecerán intactos.\n\n"
                "¿Deseas proceder?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return

        args = self.get_cli_args()
        self.request_execution.emit(args, out)
