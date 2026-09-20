"""
Entry point for whatsapp-backup-tools Graphical Interface (wab_gui).
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from wab_gui.ui.main_window import MainWindow
from wab_gui.services.adb_installer import AdbInstaller


def main():
    # Ensure ADB directory is in PATH for this process and any spawned child subprocesses
    AdbInstaller.find_adb()

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("WhatsApp Backup Tools")
    app.setOrganizationName("wabtools")

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
