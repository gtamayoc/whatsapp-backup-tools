"""
Main Archive configuration tab in Dark Carbon / iOS style.
Contains comprehensive tooltips, examples, preset loading and full parameter coverage.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QCheckBox, QSpinBox, QDateEdit, QGridLayout,
    QPushButton, QComboBox, QLineEdit, QScrollArea, QListWidget
)
from PySide6.QtCore import Qt, QDate

from wab_gui.ui.components.path_picker import PathPicker
from wab_gui.theme import (
    COLOR_DANUBE_50, COLOR_DANUBE_100, COLOR_DANUBE_200,
    COLOR_DANUBE_400, COLOR_MUTED, COLOR_DANUBE_800
)


class TabArchive(QWidget):
    """Full parameter configuration panel for archiving WhatsApp data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 4, 4, 4)

        # 1. DESTINO REQUERIDO (Output)
        card_output = QFrame()
        card_output.setObjectName("card")
        lo_out = QVBoxLayout(card_output)
        lo_out.setSpacing(6)

        lbl_out = QLabel("Directorio de Salida (Requerido)")
        lbl_out.setObjectName("h2")
        lo_out.addWidget(lbl_out)

        self.picker_output = PathPicker(
            placeholder="Ej: C:/WhatsApp_Archive",
            mode="dir",
            tooltip="Carpeta donde se guardará la estructura organizada de chats y multimedia.\nEquivalente CLI: -o / --output"
        )
        lo_out.addWidget(self.picker_output)
        layout.addWidget(card_output)

        # 2. ORIGEN DE DATOS (Mutually Exclusive Source Modes)
        card_src = QFrame()
        card_src.setObjectName("card")
        lo_src = QVBoxLayout(card_src)
        lo_src.setSpacing(10)

        lbl_src = QLabel("Origen de Datos")
        lbl_src.setObjectName("h2")
        lo_src.addWidget(lbl_src)

        # Mode selector combo
        mode_box = QHBoxLayout()
        lbl_mode = QLabel("Modo de Extracción:")
        lbl_mode.setStyleSheet(f"color: {COLOR_DANUBE_100}; font-weight: 500;")
        mode_box.addWidget(lbl_mode)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Android Local (Carpetas en Disco)",
            "Android Directo vía USB (ADB)",
            "Copia de Seguridad iPhone (iOS Backup)"
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_box.addWidget(self.combo_mode)
        mode_box.addStretch()
        lo_src.addLayout(mode_box)

        # --- Stack: Subpanels for each mode ---
        # A) Android Local Mode Panel
        self.panel_android_local = QFrame()
        lo_and_local = QVBoxLayout(self.panel_android_local)
        lo_and_local.setContentsMargins(0, 4, 0, 4)
        lo_and_local.addWidget(QLabel("Carpetas raíz de WhatsApp (wa_root):"))

        self.list_wa_roots = QListWidget()
        self.list_wa_roots.setFixedHeight(90)
        self.list_wa_roots.setStyleSheet(f"background-color: {COLOR_DANUBE_800}; border-radius: 6px;")
        lo_and_local.addWidget(self.list_wa_roots)

        btn_row_roots = QHBoxLayout()
        self.picker_root_add = PathPicker(placeholder="Seleccionar carpeta de WhatsApp (contiene Media/)...", mode="dir")
        btn_row_roots.addWidget(self.picker_root_add)

        self.btn_add_root = QPushButton("Añadir")
        self.btn_add_root.clicked.connect(self._add_root)
        btn_row_roots.addWidget(self.btn_add_root)

        self.btn_remove_root = QPushButton("Quitar")
        self.btn_remove_root.clicked.connect(self._remove_root)
        btn_row_roots.addWidget(self.btn_remove_root)
        lo_and_local.addLayout(btn_row_roots)
        lo_src.addWidget(self.panel_android_local)

        # B) Android ADB Mode Panel
        self.panel_android_adb = QFrame()
        lo_and_adb = QVBoxLayout(self.panel_android_adb)
        lo_and_adb.setContentsMargins(0, 4, 0, 4)

        self.cb_pull_media = QCheckBox("Extraer también todos los archivos multimedia (--pull-media)")
        self.cb_pull_media.setToolTip("Descarga fotos, videos, audios y documentos del teléfono mediante ADB.")
        self.cb_pull_media.toggled.connect(self._on_pull_media_toggled)
        lo_and_adb.addWidget(self.cb_pull_media)

        self.lbl_staging = QLabel("Carpeta Staging (Local persistente para multimedia ADB):")
        lo_and_adb.addWidget(self.lbl_staging)
        self.picker_staging = PathPicker(
            placeholder="Ej: C:/WhatsApp_Staging",
            mode="dir",
            tooltip="Directorio temporal local donde se guardan los archivos multimedia extraídos de ADB.\nEquivalente CLI: --staging"
        )
        lo_and_adb.addWidget(self.picker_staging)

        self.cb_business = QCheckBox("Objetivo: WhatsApp Business (--business)")
        self.cb_business.setToolTip("Usa las rutas de paquetes y bases de datos de WhatsApp Business.")
        lo_and_adb.addWidget(self.cb_business)
        lo_src.addWidget(self.panel_android_adb)

        # C) iOS Backup Mode Panel
        self.panel_ios = QFrame()
        lo_ios = QVBoxLayout(self.panel_ios)
        lo_ios.setContentsMargins(0, 4, 0, 4)

        lo_ios.addWidget(QLabel("Carpeta de Copia de Seguridad iOS (--ios-backup):"))
        self.picker_ios_backup = PathPicker(
            placeholder="Ej: C:/Users/.../Apple/MobileSync/Backup/<UDID>",
            mode="dir",
            tooltip="Carpeta que contiene el archivo Manifest.db del backup de iTunes/Finder.\nEquivalente CLI: --ios-backup"
        )
        lo_ios.addWidget(self.picker_ios_backup)

        pwd_row = QHBoxLayout()
        pwd_row.addWidget(QLabel("Contraseña de Backup Cifrado:"))
        self.input_ios_pwd = QLineEdit()
        self.input_ios_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_ios_pwd.setPlaceholderText("Solo si el backup de iPhone tiene contraseña...")
        pwd_row.addWidget(self.input_ios_pwd)

        self.cb_show_pwd = QCheckBox("Ver")
        self.cb_show_pwd.toggled.connect(
            lambda chk: self.input_ios_pwd.setEchoMode(
                QLineEdit.EchoMode.Normal if chk else QLineEdit.EchoMode.Password
            )
        )
        pwd_row.addWidget(self.cb_show_pwd)
        lo_ios.addLayout(pwd_row)

        lo_ios.addWidget(QLabel("Archivo ContactsV2.sqlite de iOS (Opcional):"))
        self.picker_ios_contacts = PathPicker(
            placeholder="Opcional (se extrae automáticamente si no se indica)",
            mode="file_open",
            file_filter="Base de datos SQLite (*.sqlite *.db)"
        )
        lo_ios.addWidget(self.picker_ios_contacts)
        lo_src.addWidget(self.panel_ios)

        layout.addWidget(card_src)

        # 3. BASES DE DATOS Y CLAVES (Database & Decryption)
        card_db = QFrame()
        card_db.setObjectName("card")
        lo_db = QVBoxLayout(card_db)
        lo_db.setSpacing(8)

        lbl_db = QLabel("Bases de Datos y Descifrado")
        lbl_db.setObjectName("h2")
        lo_db.addWidget(lbl_db)

        grid_db = QGridLayout()
        grid_db.setSpacing(8)

        grid_db.addWidget(QLabel("Archivo msgstore o ChatStorage:"), 0, 0)
        self.picker_msgstore = PathPicker(
            placeholder="msgstore.db / msgstore.db.crypt15 / ChatStorage.sqlite",
            mode="file_open",
            file_filter="WhatsApp Databases (*.db *.crypt15 *.sqlite);;Todos (*.*)",
            tooltip="Ruta a la base de datos de mensajes.\nEquivalente CLI: --msgstore"
        )
        grid_db.addWidget(self.picker_msgstore, 0, 1)

        grid_db.addWidget(QLabel("Clave de Cifrado E2E (--e2e-key):"), 1, 0)
        self.picker_e2e_key = PathPicker(
            placeholder="Ruta al archivo de clave para msgstore.db.crypt15",
            mode="file_open",
            file_filter="Key File (*.key);;Todos (*.*)",
            tooltip="Clave de 32/64 bytes para descifrar bases de datos .crypt15.\nEquivalente CLI: --e2e-key"
        )
        grid_db.addWidget(self.picker_e2e_key, 1, 1)

        grid_db.addWidget(QLabel("Archivo de Contactos Exportados (-c):"), 2, 0)
        self.picker_contacts = PathPicker(
            placeholder="Exportación de contactos Android o vCard",
            mode="file_open",
            tooltip="Archivo exportado de contactos para mapear nombres y teléfonos.\nEquivalente CLI: -c / --contacts"
        )
        grid_db.addWidget(self.picker_contacts, 2, 1)

        lo_db.addLayout(grid_db)
        layout.addWidget(card_db)

        # 4. PARÁMETROS AVANZADOS Y FILTROS
        card_adv = QFrame()
        card_adv.setObjectName("card")
        lo_adv = QVBoxLayout(card_adv)
        lo_adv.setSpacing(8)

        lbl_adv = QLabel("Filtros y Parámetros de Ejecución")
        lbl_adv.setObjectName("h2")
        lo_adv.addWidget(lbl_adv)

        grid_adv = QGridLayout()
        grid_adv.setSpacing(8)

        # Since date filter
        self.cb_since = QCheckBox("Filtrar desde fecha (--since):")
        self.cb_since.toggled.connect(self._toggle_since)
        grid_adv.addWidget(self.cb_since, 0, 0)

        self.date_since = QDateEdit()
        self.date_since.setCalendarPopup(True)
        self.date_since.setDate(QDate.currentDate().addYears(-1))
        self.date_since.setEnabled(False)
        self.date_since.setDisplayFormat("yyyy-MM-dd")
        grid_adv.addWidget(self.date_since, 0, 1)

        # Limit
        self.cb_limit = QCheckBox("Límite de mensajes de prueba (--limit):")
        self.cb_limit.toggled.connect(self._toggle_limit)
        grid_adv.addWidget(self.cb_limit, 1, 0)

        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 500000)
        self.spin_limit.setValue(250)
        self.spin_limit.setEnabled(False)
        grid_adv.addWidget(self.spin_limit, 1, 1)

        # Timezone
        grid_adv.addWidget(QLabel("Zona Horaria (--timezone):"), 2, 0)
        self.input_tz = QLineEdit()
        self.input_tz.setPlaceholderText("Ej: America/Bogota, Europe/Madrid, UTC (por defecto: hora local)")
        grid_adv.addWidget(self.input_tz, 2, 1)

        # Dry Run
        self.cb_dry_run = QCheckBox("Modo Simulación (--dry-run) — Sin copiar archivos reales")
        self.cb_dry_run.setStyleSheet(f"color: {COLOR_DANUBE_200}; font-weight: 600;")
        grid_adv.addWidget(self.cb_dry_run, 3, 0, 1, 2)

        lo_adv.addLayout(grid_adv)
        layout.addWidget(card_adv)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Set initial visibility
        self._on_mode_changed(0)
        self._on_pull_media_toggled(False)

    def _on_mode_changed(self, index: int):
        self.panel_android_local.setVisible(index == 0)
        self.panel_android_adb.setVisible(index == 1)
        self.panel_ios.setVisible(index == 2)

    def _on_pull_media_toggled(self, checked: bool):
        self.lbl_staging.setEnabled(checked)
        self.picker_staging.setEnabled(checked)

    def _toggle_since(self, checked: bool):
        self.date_since.setEnabled(checked)

    def _toggle_limit(self, checked: bool):
        self.spin_limit.setEnabled(checked)

    def _add_root(self):
        p = self.picker_root_add.get_path()
        if p and p not in [self.list_wa_roots.item(i).text() for i in range(self.list_wa_roots.count())]:
            self.list_wa_roots.addItem(p)
            self.picker_root_add.set_path("")

    def _remove_root(self):
        sel = self.list_wa_roots.currentRow()
        if sel >= 0:
            self.list_wa_roots.takeItem(sel)

    def get_cli_args(self) -> list[str]:
        """Convert current form selections to exact CLI flags for wab-archiver."""
        args = ["-m", "wab_archiver", "archive"]

        out = self.picker_output.get_path()
        if out:
            args.extend(["-o", out])

        mode = self.combo_mode.currentIndex()
        if mode == 0:  # Android Local
            for i in range(self.list_wa_roots.count()):
                args.extend(["--wa-root", self.list_wa_roots.item(i).text()])
        elif mode == 1:  # Android ADB
            args.append("--from-adb")
            if self.cb_pull_media.isChecked():
                args.append("--pull-media")
                stg = self.picker_staging.get_path()
                if stg:
                    args.extend(["--staging", stg])
            if self.cb_business.isChecked():
                args.append("--business")
        elif mode == 2:  # iOS
            ios_b = self.picker_ios_backup.get_path()
            if ios_b:
                args.extend(["--ios-backup", ios_b])
            pwd = self.input_ios_pwd.text().strip()
            if pwd:
                args.extend(["--ios-password", pwd])
            ios_c = self.picker_ios_contacts.get_path()
            if ios_c:
                args.extend(["--ios-contacts", ios_c])

        # Msgstore & keys
        msg = self.picker_msgstore.get_path()
        if msg:
            args.extend(["--msgstore", msg])

        key = self.picker_e2e_key.get_path()
        if key:
            args.extend(["--e2e-key", key])

        cnt = self.picker_contacts.get_path()
        if cnt:
            args.extend(["-c", cnt])

        # Advanced
        if self.cb_since.isChecked():
            args.extend(["--since", self.date_since.date().toString("yyyy-MM-dd")])

        if self.cb_limit.isChecked():
            args.extend(["--limit", str(self.spin_limit.value())])

        tz = self.input_tz.text().strip()
        if tz:
            args.extend(["--timezone", tz])

        if self.cb_dry_run.isChecked():
            args.append("--dry-run")

        return args

    def get_config_dict(self) -> dict:
        """Returns standard dictionary compatible with config.toml."""
        d = {}
        out = self.picker_output.get_path()
        if out:
            d["output"] = out

        mode = self.combo_mode.currentIndex()
        if mode == 0:
            roots = [self.list_wa_roots.item(i).text() for i in range(self.list_wa_roots.count())]
            if roots:
                d["wa_root"] = roots if len(roots) > 1 else roots[0]
        elif mode == 1:
            if self.cb_pull_media.isChecked():
                d["pull_media"] = True
                stg = self.picker_staging.get_path()
                if stg:
                    d["staging"] = stg
            if self.cb_business.isChecked():
                d["business"] = True
        elif mode == 2:
            ios_b = self.picker_ios_backup.get_path()
            if ios_b:
                d["ios_backup"] = ios_b
            pwd = self.input_ios_pwd.text().strip()
            if pwd:
                d["ios_password"] = pwd
            ios_c = self.picker_ios_contacts.get_path()
            if ios_c:
                d["ios_contacts"] = ios_c

        msg = self.picker_msgstore.get_path()
        if msg:
            d["msgstore"] = msg
        key = self.picker_e2e_key.get_path()
        if key:
            d["e2e_key"] = key
        cnt = self.picker_contacts.get_path()
        if cnt:
            d["contacts"] = cnt
        if self.cb_since.isChecked():
            d["since"] = self.date_since.date().toString("yyyy-MM-dd")
        tz = self.input_tz.text().strip()
        if tz:
            d["timezone"] = tz

        return d

    def apply_config_dict(self, cfg: dict):
        """Populate UI fields from a config.toml dictionary."""
        if "output" in cfg:
            self.picker_output.set_path(str(cfg["output"]))

        # Check source modes
        if "ios_backup" in cfg:
            self.combo_mode.setCurrentIndex(2)
            self.picker_ios_backup.set_path(str(cfg["ios_backup"]))
            if "ios_password" in cfg:
                self.input_ios_pwd.setText(str(cfg["ios_password"]))
            if "ios_contacts" in cfg:
                self.picker_ios_contacts.set_path(str(cfg["ios_contacts"]))
        elif "pull_media" in cfg or "staging" in cfg:
            self.combo_mode.setCurrentIndex(1)
            self.cb_pull_media.setChecked(bool(cfg.get("pull_media", False)))
            if "staging" in cfg:
                self.picker_staging.set_path(str(cfg["staging"]))
            if "business" in cfg:
                self.cb_business.setChecked(bool(cfg["business"]))
        elif "wa_root" in cfg:
            self.combo_mode.setCurrentIndex(0)
            self.list_wa_roots.clear()
            val = cfg["wa_root"]
            if isinstance(val, list):
                for v in val:
                    self.list_wa_roots.addItem(str(v))
            else:
                self.list_wa_roots.addItem(str(val))

        if "msgstore" in cfg:
            self.picker_msgstore.set_path(str(cfg["msgstore"]))
        if "e2e_key" in cfg:
            self.picker_e2e_key.set_path(str(cfg["e2e_key"]))
        if "contacts" in cfg:
            self.picker_contacts.set_path(str(cfg["contacts"]))
        if "timezone" in cfg:
            self.input_tz.setText(str(cfg["timezone"]))
        if "since" in cfg:
            self.cb_since.setChecked(True)
            dt = QDate.fromString(str(cfg["since"]), "yyyy-MM-dd")
            if dt.isValid():
                self.date_since.setDate(dt)
