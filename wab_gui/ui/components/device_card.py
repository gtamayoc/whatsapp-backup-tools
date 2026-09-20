"""
Visual card for device status and diagnostics (Dark Carbon / iOS styled).
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, Signal

from wab_gui.services.adb_service import DeviceInfo
from wab_gui.theme import (
    COLOR_DANUBE_50, COLOR_DANUBE_100, COLOR_DANUBE_200,
    COLOR_DANUBE_400, COLOR_DANUBE_600, COLOR_DANUBE_800, COLOR_SUCCESS,
    COLOR_WARNING, COLOR_ERROR, COLOR_MUTED
)


class DeviceCard(QFrame):
    """Visual card displaying phone hardware, battery, authorization status and storage."""

    refresh_requested = Signal()
    install_adb_requested = Signal()
    use_path_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)

        # Header row: Title + Status Badge + Refresh
        header_layout = QHBoxLayout()

        self.title = QLabel("Dispositivo Android (USB)")
        self.title.setObjectName("h2")
        header_layout.addWidget(self.title)

        self.status_badge = QLabel("Buscando...")
        self.status_badge.setStyleSheet(f"""
            background-color: {COLOR_DANUBE_800};
            color: {COLOR_MUTED};
            border-radius: 6px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        self.btn_install_adb = QPushButton("⚡ Descargar / Configurar ADB")
        self.btn_install_adb.setStyleSheet(f"background-color: {COLOR_DANUBE_600}; color: #ffffff; font-weight: 500;")
        self.btn_install_adb.setToolTip("Descarga automáticamente Google Platform-Tools (ADB) y lo configura en el PATH del sistema.")
        self.btn_install_adb.setVisible(False)
        self.btn_install_adb.clicked.connect(self.install_adb_requested.emit)
        header_layout.addWidget(self.btn_install_adb)

        self.btn_refresh = QPushButton("Escanear")
        self.btn_refresh.setToolTip("Buscar dispositivos Android conectados por USB")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.btn_refresh)

        main_layout.addLayout(header_layout)

        # Info Grid
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(4)

        # Model & Manufacturer
        self.lbl_model_key = QLabel("Modelo:")
        self.lbl_model_key.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        self.lbl_model_val = QLabel("—")
        self.lbl_model_val.setStyleSheet(f"color: {COLOR_DANUBE_50}; font-weight: 500;")
        self.grid.addWidget(self.lbl_model_key, 0, 0)
        self.grid.addWidget(self.lbl_model_val, 0, 1)

        # Android Version & SDK
        self.lbl_os_key = QLabel("Sistema:")
        self.lbl_os_key.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        self.lbl_os_val = QLabel("—")
        self.lbl_os_val.setStyleSheet(f"color: {COLOR_DANUBE_50}; font-weight: 500;")
        self.grid.addWidget(self.lbl_os_key, 0, 2)
        self.grid.addWidget(self.lbl_os_val, 0, 3)

        # Battery
        self.lbl_bat_key = QLabel("Batería:")
        self.lbl_bat_key.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        self.lbl_bat_val = QLabel("—")
        self.lbl_bat_val.setStyleSheet(f"color: {COLOR_DANUBE_50}; font-weight: 500;")
        self.grid.addWidget(self.lbl_bat_key, 1, 0)
        self.grid.addWidget(self.lbl_bat_val, 1, 1)

        # Serial
        self.lbl_sn_key = QLabel("Serial:")
        self.lbl_sn_key.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        self.lbl_sn_val = QLabel("—")
        self.lbl_sn_val.setStyleSheet(f"color: {COLOR_DANUBE_200}; font-family: monospace;")
        self.grid.addWidget(self.lbl_sn_key, 1, 2)
        self.grid.addWidget(self.lbl_sn_val, 1, 3)

        main_layout.addLayout(self.grid)

        # Storage bar
        storage_box = QVBoxLayout()
        storage_box.setSpacing(4)

        self.storage_label = QLabel("Almacenamiento: Desconectado")
        self.storage_label.setStyleSheet(f"color: {COLOR_DANUBE_100}; font-size: 11px;")
        storage_box.addWidget(self.storage_label)

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(0)
        storage_box.addWidget(self.storage_bar)

        main_layout.addLayout(storage_box)

        # Paths notice
        self.paths_box = QLabel("Rutas WhatsApp: Conecte el dispositivo para comprobar ubicaciones.")
        self.paths_box.setWordWrap(True)
        self.paths_box.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px; padding: 4px 0;")
        main_layout.addWidget(self.paths_box)

    def set_no_device(self, adb_available: bool = True):
        if not adb_available:
            self.status_badge.setText("ADB No Encontrado")
            self.status_badge.setStyleSheet(f"background-color: {COLOR_ERROR}; color: #fff; border-radius: 6px; padding: 2px 8px; font-weight: bold;")
            self.paths_box.setText("❌ No se encontró 'adb'. Haga clic en '⚡ Descargar / Configurar ADB' para instalarlo automáticamente.")
            self.btn_install_adb.setVisible(True)
        else:
            self.status_badge.setText("Sin Dispositivo")
            self.status_badge.setStyleSheet(f"background-color: {COLOR_DANUBE_800}; color: {COLOR_MUTED}; border-radius: 6px; padding: 2px 8px; font-weight: bold;")
            self.paths_box.setText("Conecte su teléfono Android mediante cable USB con Depuración activada.")
            self.btn_install_adb.setVisible(False)

        self.lbl_model_val.setText("—")
        self.lbl_os_val.setText("—")
        self.lbl_bat_val.setText("—")
        self.lbl_sn_val.setText("—")
        self.storage_label.setText("Almacenamiento: Desconectado")
        self.storage_bar.setValue(0)

    def set_device_info(self, info: DeviceInfo):
        if info.state == "unauthorized":
            self.btn_install_adb.setVisible(False)
            self.status_badge.setText("No Autorizado")
            self.status_badge.setStyleSheet(f"background-color: {COLOR_WARNING}; color: #000; border-radius: 6px; padding: 2px 8px; font-weight: bold;")
            self.paths_box.setText("⚠️ Desbloquee su teléfono y acepte el mensaje emergente en pantalla: '¿Permitir depuración USB?'.")
            self.lbl_sn_val.setText(info.serial)
            return

        if info.state == "device":
            self.btn_install_adb.setVisible(False)
            self.status_badge.setText("Conectado")
            self.status_badge.setStyleSheet(f"background-color: {COLOR_SUCCESS}; color: #010b18; border-radius: 6px; padding: 2px 8px; font-weight: bold;")

            self.lbl_model_val.setText(f"{info.manufacturer} {info.model}")
            self.lbl_os_val.setText(f"Android {info.android_version} (API {info.sdk_level})")

            bat_str = f"{info.battery_level}%" if info.battery_level is not None else "N/A"
            if info.is_charging:
                bat_str += " ⚡ (Cargando)"
            self.lbl_bat_val.setText(bat_str)
            self.lbl_sn_val.setText(info.serial)

            # Storage
            if info.storage_percent is not None:
                self.storage_bar.setValue(info.storage_percent)
                self.storage_label.setText(
                    f"Almacenamiento: {info.storage_used} usados de {info.storage_total} ({info.storage_free} libres)"
                )
            else:
                self.storage_bar.setValue(0)
                self.storage_label.setText("Almacenamiento: Información no disponible")

            # WhatsApp Paths summary
            found_paths = [name for name, exists in info.whatsapp_paths.items() if exists]
            if found_paths:
                db_txt = " | Base de datos msgstore.db.crypt15: Encontrada" if info.has_msgstore_crypt else ""
                self.paths_box.setText(f"✓ Ubicaciones WhatsApp detectadas: {', '.join(found_paths)}{db_txt}")
                self.paths_box.setStyleSheet(f"color: {COLOR_SUCCESS}; font-size: 11px;")
            else:
                self.paths_box.setText("No se detectaron carpetas estándar de WhatsApp en almacenamiento compartido.")
                self.paths_box.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 11px;")
