"""
Main application window for wab_gui.
Combines tabs, ADB inspection card, preset manager, execution runner and theme.
"""

from __future__ import annotations
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLabel, QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal

from wab_gui.theme import MAIN_STYLESHEET, COLOR_DANUBE_50, COLOR_DANUBE_100, COLOR_DANUBE_200
from wab_gui.ui.components.device_card import DeviceCard
from wab_gui.ui.tabs.tab_archive import TabArchive
from wab_gui.ui.tabs.tab_restore import TabRestore
from wab_gui.ui.tabs.tab_execution import TabExecution
from wab_gui.services.adb_service import AdbService
from wab_gui.services.config_service import ConfigService
from wab_gui.workers.runner_worker import RunnerWorker


class AdbScanWorker(QThread):
    """Background worker for non-blocking ADB polling."""

    device_found = Signal(object)
    scan_failed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        if not AdbService.is_adb_installed():
            self.scan_failed.emit(False)
            return

        devices = AdbService.list_devices()
        if not devices:
            self.scan_failed.emit(True)
            return

        # Inspect the first connected device
        dev = devices[0]
        if dev.state == "device":
            full_dev = AdbService.inspect_device(dev.serial)
            self.device_found.emit(full_dev)
        else:
            self.device_found.emit(dev)


class MainWindow(QMainWindow):
    """Main window for whatsapp-backup-tools GUI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WhatsApp Backup Tools — GUI")
        self.resize(950, 750)
        self.setStyleSheet(MAIN_STYLESHEET)

        self.current_worker: RunnerWorker | None = None
        self.adb_worker: AdbScanWorker | None = None
        self.install_worker: QThread | None = None

        self._init_ui()
        self._refresh_presets()
        self._start_adb_scan()

    def closeEvent(self, event):
        if self.adb_worker and self.adb_worker.isRunning():
            self.adb_worker.quit()
            self.adb_worker.wait(1000)
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(1000)
        super().closeEvent(event)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Top Header & Presets Bar
        header_bar = QHBoxLayout()

        title_box = QVBoxLayout()
        lbl_app = QLabel("WhatsApp Backup Tools")
        lbl_app.setObjectName("h1")
        title_box.addWidget(lbl_app)

        lbl_desc = QLabel("Capa de gestión, diagnóstico ADB y archivado offline de chats")
        lbl_desc.setObjectName("subtitle")
        title_box.addWidget(lbl_desc)
        header_bar.addLayout(title_box)

        header_bar.addStretch()

        # Preset manager controls
        header_bar.addWidget(QLabel("Preset:"))
        self.combo_presets = QComboBox()
        self.combo_presets.setMinimumWidth(140)
        header_bar.addWidget(self.combo_presets)

        self.btn_load_preset = QPushButton("Cargar")
        self.btn_load_preset.clicked.connect(self._load_selected_preset)
        header_bar.addWidget(self.btn_load_preset)

        self.btn_save_preset = QPushButton("Guardar Como...")
        self.btn_save_preset.clicked.connect(self._save_new_preset)
        header_bar.addWidget(self.btn_save_preset)

        self.btn_import_toml = QPushButton("Importar TOML")
        self.btn_import_toml.clicked.connect(self._import_toml)
        header_bar.addWidget(self.btn_import_toml)

        main_layout.addLayout(header_bar)

        # 2. ADB Device Diagnostics Card
        self.device_card = DeviceCard()
        self.device_card.refresh_requested.connect(self._start_adb_scan)
        self.device_card.install_adb_requested.connect(self._handle_install_adb)
        main_layout.addWidget(self.device_card)

        # 3. Main Tabs
        self.tabs = QTabWidget()

        self.tab_archive = TabArchive()
        self.tabs.addTab(self.tab_archive, "Archivar Multimedia")

        self.tab_restore = TabRestore()
        self.tabs.addTab(self.tab_restore, "Restaurar Copia")

        self.tab_execution = TabExecution()
        self.tabs.addTab(self.tab_execution, "Consola y Progreso")

        main_layout.addWidget(self.tabs)

        # 4. Bottom Execution Action Bar
        bottom_bar = QHBoxLayout()

        self.btn_start = QPushButton("▶ Iniciar Operación")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.clicked.connect(self._start_operation)
        bottom_bar.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("⏹ Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_operation)
        bottom_bar.addWidget(self.btn_cancel)

        bottom_bar.addStretch()

        lbl_footer = QLabel("Diseño Dark Carbon • Danube Theme")
        lbl_footer.setStyleSheet(f"color: {COLOR_DANUBE_200}; font-size: 11px;")
        bottom_bar.addWidget(lbl_footer)

        main_layout.addLayout(bottom_bar)

    def _start_adb_scan(self):
        self.device_card.status_badge.setText("Escaneando...")
        self.adb_worker = AdbScanWorker(self)
        self.adb_worker.device_found.connect(self.device_card.set_device_info)
        self.adb_worker.scan_failed.connect(self.device_card.set_no_device)
        self.adb_worker.start()

    def _handle_install_adb(self):
        from PySide6.QtWidgets import QProgressDialog
        from wab_gui.services.adb_installer import AdbInstaller

        prog = QProgressDialog("Descargando Google Platform-Tools (ADB)...", "Cancelar", 0, 100, self)
        prog.setWindowTitle("Configuración Automática de ADB")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(5)

        class InstallThread(QThread):
            progress_sig = Signal(int, str)
            done_sig = Signal(bool, str)

            def run(self):
                def cb(pct, msg):
                    self.progress_sig.emit(pct, msg)

                bin_path = AdbInstaller.download_and_install_adb(progress_callback=cb)
                if bin_path:
                    self.done_sig.emit(True, bin_path)
                else:
                    self.done_sig.emit(False, "No se pudo completar la instalación de ADB.")

        thread = InstallThread(self)
        self.install_worker = thread

        def on_prog(pct, msg):
            prog.setValue(pct)
            prog.setLabelText(msg)

        def on_done(ok, msg):
            prog.close()
            if ok:
                QMessageBox.information(
                    self,
                    "ADB Configurado con Éxito",
                    f"Android Platform-Tools se ha instalado y configurado en el sistema:\n\n{msg}\n\n"
                    "El comando 'adb' ahora está disponible tanto en la interfaz como en nuevas terminales de Windows."
                )
                self._start_adb_scan()
            else:
                QMessageBox.critical(self, "Error de Instalación", f"Ocurrió un error:\n{msg}")

        thread.progress_sig.connect(on_prog)
        thread.done_sig.connect(on_done)
        prog.canceled.connect(thread.terminate)
        thread.start()

    def _refresh_presets(self):
        presets = ConfigService.list_presets()
        self.combo_presets.clear()
        if presets:
            self.combo_presets.addItems(presets)
        else:
            self.combo_presets.addItem("(Sin presets guardados)")

    def _load_selected_preset(self):
        name = self.combo_presets.currentText()
        if not name or name.startswith("("):
            return
        cfg = ConfigService.load_preset(name)
        if cfg:
            self.tab_archive.apply_config_dict(cfg)
            QMessageBox.information(self, "Preset Cargado", f"Se cargó el perfil: {name}")

    def _save_new_preset(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Guardar Preset", "Nombre del perfil (ej: Mi_Samsung_S23):")
        if ok and name.strip():
            clean_name = name.strip().replace(" ", "_")
            cfg = self.tab_archive.get_config_dict()
            if ConfigService.save_preset(clean_name, cfg):
                self._refresh_presets()
                idx = self.combo_presets.findText(clean_name)
                if idx >= 0:
                    self.combo_presets.setCurrentIndex(idx)
                QMessageBox.information(self, "Guardado", f"Preset '{clean_name}' guardado en .wab_gui_profiles/")

    def _import_toml(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Configuración TOML", "", "Config TOML (*.toml);;Todos (*.*)")
        if path:
            cfg = ConfigService.load_toml(path)
            if cfg:
                self.tab_archive.apply_config_dict(cfg)
                QMessageBox.information(self, "Importado", f"Configuración cargada desde:\n{path}")
            else:
                QMessageBox.warning(self, "Error", "No se pudieron extraer claves válidas del archivo TOML.")

    def _start_operation(self):
        current_tab_idx = self.tabs.currentIndex()

        if current_tab_idx == 0:
            # Archive
            cli_args = self.tab_archive.get_cli_args()
            output_dir = self.tab_archive.picker_output.get_path()
            if not output_dir:
                QMessageBox.warning(self, "Campo Requerido", "Debe especificar un directorio de salida (-o / --output).")
                return
        elif current_tab_idx == 1:
            # Restore
            cli_args = self.tab_restore.get_cli_args()
            output_dir = self.tab_restore.picker_output.get_path()
            if not output_dir:
                QMessageBox.warning(self, "Campo Requerido", "Debe especificar la carpeta del archivo a restaurar (-o / --output).")
                return
        else:
            QMessageBox.information(self, "Aviso", "Seleccione la pestaña de Archivar o Restaurar para iniciar.")
            return

        # Switch to Execution Tab
        self.tabs.setCurrentIndex(2)
        self.tab_execution.set_output_dir(output_dir)
        self.tab_execution.set_running(True)
        self.tab_execution.console.clear()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        # Launch background runner worker
        self.current_worker = RunnerWorker(cli_args)
        self.current_worker.log_received.connect(self.tab_execution.console.append_log)
        self.current_worker.progress_updated.connect(self.tab_execution.update_progress)
        self.current_worker.finished_with_code.connect(self._on_operation_finished)
        self.current_worker.start()

    def _cancel_operation(self):
        if self.current_worker:
            self.current_worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _on_operation_finished(self, return_code: int):
        self.tab_execution.on_finished(return_code)
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.current_worker = None
