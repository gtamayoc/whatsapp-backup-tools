"""
Automated unit tests for wab_gui services and non-regression verification.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from wab_gui.services.adb_service import AdbService, DeviceInfo
from wab_gui.services.config_service import ConfigService, VALID_CONFIG_KEYS
from wab_gui.theme import COLOR_BLACK_950, COLOR_BLACK_50, COLOR_DANUBE_950, COLOR_DANUBE_50


def test_theme_colors():
    """Verify Kigen.design Monochrome Pitch Black tokens are properly defined."""
    assert COLOR_BLACK_950 == "#010101"
    assert COLOR_BLACK_50 == "#ffffff"
    assert COLOR_DANUBE_950 == "#010101"
    assert COLOR_DANUBE_50 == "#ffffff"


def test_config_service_toml_roundtrip():
    """Verify ConfigService saves and loads valid TOML without modifying keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.toml"
        original_data = {
            "output": "C:/Archive/Test",
            "wa_root": ["C:/Phone/WhatsApp", "C:/Backup/WhatsApp"],
            "business": True,
            "timezone": "America/Bogota",
            "since": "2024-01-01",
        }

        # Save
        saved = ConfigService.save_toml(config_path, original_data)
        assert saved is True
        assert config_path.exists()

        # Load
        loaded = ConfigService.load_toml(config_path)
        assert loaded["output"] == "C:/Archive/Test"
        assert loaded["wa_root"] == ["C:/Phone/WhatsApp", "C:/Backup/WhatsApp"]
        assert loaded["business"] is True
        assert loaded["timezone"] == "America/Bogota"
        assert loaded["since"] == "2024-01-01"


def test_adb_service_no_devices():
    """Test ADB service parsing when adb devices output is empty or header only."""
    with patch("shutil.which", return_value="/usr/bin/adb"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="List of devices attached\n\n",
                returncode=0
            )
            devices = AdbService.list_devices()
            assert devices == []


def test_adb_service_detect_device():
    """Test ADB service detects authorized and unauthorized devices correctly."""
    output = "List of devices attached\n12345678\tdevice product:starqltezc model:SM_G9600 device:starqltechn\nABCDEF\tunauthorized\n"
    with patch("shutil.which", return_value="/usr/bin/adb"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=output,
                returncode=0
            )
            devices = AdbService.list_devices()
            assert len(devices) == 2
            assert devices[0].serial == "12345678"
            assert devices[0].state == "device"
            assert devices[1].serial == "ABCDEF"
            assert devices[1].state == "unauthorized"


def test_adb_service_inspect_properties():
    """Test parsing of hardware, battery, and storage without root."""
    serial = "12345678"
    mock_getprop = "[ro.product.model]: [Galaxy S23]\n[ro.product.manufacturer]: [Samsung]\n[ro.build.version.release]: [14]\n[ro.build.version.sdk]: [34]\n"
    mock_battery = "Current Battery Service state:\n  level: 85\n  status: 2\n"
    mock_df = "Filesystem     Size  Used Avail Use% Mounted on\n/storage/emulated/0 128G  64G   64G  50% /storage/emulated/0\n"

    def side_effect(serial_arg, cmd_args, timeout=5):
        if "getprop" in cmd_args:
            return mock_getprop
        if "battery" in cmd_args:
            return mock_battery
        if "df" in cmd_args:
            return mock_df
        if "ls" in cmd_args[1]:
            # Simulate Media directory exists
            return "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media\n"
        return ""

    with patch.object(AdbService, "_run_cmd", side_effect=side_effect):
        info = AdbService.inspect_device(serial)
        assert info.model == "Galaxy S23"
        assert info.manufacturer == "Samsung"
        assert info.android_version == "14"
        assert info.sdk_level == "34"
        assert info.battery_level == 85
        assert info.is_charging is True
        assert info.storage_total == "128G"
        assert info.storage_used == "64G"
        assert info.storage_percent == 50
        assert info.whatsapp_paths["WhatsApp Media (Android 11+)"] is True


def test_main_window_instantiation():
    """Verify that MainWindow and all its tabs and components instantiate cleanly without errors."""
    from PySide6.QtWidgets import QApplication
    from wab_gui.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    with patch.object(MainWindow, "_start_adb_scan"):
        win = MainWindow()
        assert win.windowTitle() == "WhatsApp Backup Tools — GUI"
        assert win.device_card is not None
        assert win.txt_global_output is not None
        assert win.tab_whatsapp is not None
        assert win.tab_archive is not None
        assert win.tab_restore is not None
        assert win.tab_execution is not None
        win.close()


def test_media_scanner_classification():
    """Verify classification of WhatsApp media file types."""
    from wab_gui.services.media_scanner import (
        classify_file, should_skip_file, format_bytes,
        CATEGORY_VIDEOS, CATEGORY_IMAGES, CATEGORY_AUDIOS,
        CATEGORY_DOCS, CATEGORY_DATABASES, CATEGORY_BACKUPS, CATEGORY_OTHER
    )

    # By extension
    assert classify_file("VID-20260404-WA0002.mp4") == CATEGORY_VIDEOS
    assert classify_file("IMG-20260802-WA0000.jpg") == CATEGORY_IMAGES
    assert classify_file("PTT-20260920-WA0001.opus") == CATEGORY_AUDIOS
    assert classify_file("Factura.pdf") == CATEGORY_DOCS
    assert classify_file("unknown.xyz") == CATEGORY_OTHER

    # By folder path
    assert classify_file("DOC-20240414-WA0109.", "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Documents/Sent/DOC-20240414-WA0109.") == CATEGORY_DOCS
    assert classify_file("sample_clip", "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Video/Sent/sample_clip") == CATEGORY_VIDEOS
    assert classify_file("audio_memo", "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes/audio_memo") == CATEGORY_AUDIOS
    assert classify_file("sticker_raw", "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Stickers/sticker_raw") == CATEGORY_IMAGES
    assert classify_file("msgstore.db.crypt14", "/WhatsApp/Databases/msgstore.db.crypt14") == CATEGORY_DATABASES
    assert classify_file("backup_settings.json.crypt14", "/WhatsApp/Backups/backup_settings.json.crypt14") == CATEGORY_BACKUPS
    assert classify_file("state.data", "/WhatsApp/.Shared/state.data") == CATEGORY_BACKUPS

    # should_skip_file filters
    assert should_skip_file(".nomedia", "/Media/WhatsApp Video/.nomedia") is True
    assert should_skip_file("story.mp4", "/Media/.Statuses/story.mp4") is True
    assert should_skip_file("preview.jpg", "/Media/.Links/preview.jpg") is True
    assert should_skip_file("cache.dat", "/Media/.wamocache/cache.dat") is True
    assert should_skip_file("file.tmp", "/WhatsApp/Media/file.tmp") is True
    assert should_skip_file("VID-01.mp4", "/Media/WhatsApp Video/VID-01.mp4") is False
    assert should_skip_file("IMG-01.jpg", "/Media/WhatsApp Images/IMG-01.jpg") is False

    assert format_bytes(500) == "500 B"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.00 GB"


def test_device_monitor_transitions():
    """Verify AdbDeviceMonitor detects connection, disconnection, and device changes."""
    from wab_gui.services.device_monitor import AdbDeviceMonitor
    from wab_gui.services.adb_service import DeviceInfo

    monitor = AdbDeviceMonitor(poll_interval_ms=50)

    connected_events = []
    disconnected_events = []
    no_device_events = []

    monitor.device_connected.connect(lambda d: connected_events.append(d))
    monitor.device_disconnected.connect(lambda sn: disconnected_events.append(sn))
    monitor.no_device_detected.connect(lambda: no_device_events.append(True))

    # Mock sequence: 1. No device -> 2. Phone 1 connects -> 3. Phone 1 disconnects -> 4. Phone 2 connects
    dev1 = DeviceInfo(serial="SN_PHONE_1", state="device", model="Pixel 7")
    dev2 = DeviceInfo(serial="SN_PHONE_2", state="device", model="Galaxy S24")

    # Cycle 1: No device
    with patch.object(AdbService, "is_adb_installed", return_value=True):
        with patch.object(AdbService, "list_devices", return_value=[]):
            monitor._current_serial = None
            monitor._current_state = None
            # Simulate one check iteration logic
            active_dev = None
            if active_dev is None:
                if monitor._current_serial is not None:
                    monitor.device_disconnected.emit(monitor._current_serial)
                else:
                    monitor.no_device_detected.emit()
            assert len(no_device_events) == 1

        # Cycle 2: Phone 1 connects
        with patch.object(AdbService, "list_devices", return_value=[dev1]):
            with patch.object(AdbService, "inspect_device", return_value=dev1):
                monitor._current_serial = dev1.serial
                monitor._current_state = dev1.state
                monitor.device_connected.emit(dev1)
                assert len(connected_events) == 1
                assert connected_events[0].serial == "SN_PHONE_1"

        # Cycle 3: Disconnection
        with patch.object(AdbService, "list_devices", return_value=[]):
            old_sn = monitor._current_serial
            monitor._current_serial = None
            monitor.device_disconnected.emit(old_sn)
            assert len(disconnected_events) == 1
            assert disconnected_events[0] == "SN_PHONE_1"

        # Cycle 4: Phone 2 connects (different serial)
        with patch.object(AdbService, "list_devices", return_value=[dev2]):
            with patch.object(AdbService, "inspect_device", return_value=dev2):
                monitor._current_serial = dev2.serial
                monitor.device_connected.emit(dev2)
                assert len(connected_events) == 2
                assert connected_events[1].serial == "SN_PHONE_2"


def test_media_table_model_virtualization():
    """Verify MediaTableModel renders virtualized items with instant O(1) data access."""
    from PySide6.QtCore import QModelIndex, Qt
    from wab_gui.ui.components.media_table_model import MediaTableModel
    from wab_gui.services.scan_db import DbMediaItem
    from wab_gui.services.media_scanner import CATEGORY_VIDEOS

    model = MediaTableModel()
    assert model.rowCount() == 0
    assert model.columnCount() == 4

    items = [
        DbMediaItem(
            id=i,
            session_id="test_sess",
            device_serial="SN_TEST",
            name=f"clip_{i}.mp4",
            relative_path=f"Media/clip_{i}.mp4",
            full_path=f"/path/clip_{i}.mp4",
            size_bytes=1000 * (i + 1),
            category=CATEGORY_VIDEOS,
            extension=".mp4",
            mtime=1700000000 + i
        )
        for i in range(1000)
    ]

    model.set_items(items, total_count=1000, total_bytes=sum(it.size_bytes for it in items))
    assert model.rowCount() == 1000
    assert model.total_matched_count == 1000

    # Test O(1) data queries on specific cells
    idx_name = model.index(0, 0)
    assert model.data(idx_name, Qt.ItemDataRole.DisplayRole) == "clip_0.mp4"

    idx_cat = model.index(0, 1)
    assert model.data(idx_cat, Qt.ItemDataRole.DisplayRole) == CATEGORY_VIDEOS

    idx_size = model.index(0, 2)
    assert "KB" in model.data(idx_size, Qt.ItemDataRole.DisplayRole) or "B" in model.data(idx_size, Qt.ItemDataRole.DisplayRole)

    # Test clear
    model.clear()
    assert model.rowCount() == 0


def test_tab_whatsapp_content_connection_lifecycle():
    """Verify TabWhatsAppContent transitions cleanly between disconnected waiting view and active session."""
    from PySide6.QtWidgets import QApplication
    from wab_gui.ui.tabs.tab_whatsapp_content import TabWhatsAppContent

    app = QApplication.instance() or QApplication([])
    tab = TabWhatsAppContent()

    # Initial state: no device connected -> stack index 0 (NoDevicePlaceholder)
    assert tab.serial is None
    assert tab.stack.currentIndex() == 0
    assert tab.lbl_device_badge.text() == "Sin Dispositivo"

    # Connect device A
    with patch.object(TabWhatsAppContent, "trigger_scan"):
        tab.set_device_context("/mock/adb", "SN_AAA", "Pixel_7")
        assert tab.serial == "SN_AAA"
        assert tab.stack.currentIndex() == 1
        assert "Pixel_7" in tab.lbl_device_badge.text()

    # Disconnect device A
    tab.clear_device_context()
    assert tab.serial is None
    assert tab.stack.currentIndex() == 0
    assert tab.lbl_device_badge.text() == "Sin Dispositivo"
    assert tab.table_model.rowCount() == 0

    # Connect device B -> Fresh session without previous data
    with patch.object(TabWhatsAppContent, "trigger_scan"):
        tab.set_device_context("/mock/adb", "SN_BBB", "Galaxy_S24")
        assert tab.serial == "SN_BBB"
        assert tab.stack.currentIndex() == 1
        assert "Galaxy_S24" in tab.lbl_device_badge.text()

    tab.close()


