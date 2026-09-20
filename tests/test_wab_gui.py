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
from wab_gui.theme import COLOR_DANUBE_950, COLOR_DANUBE_50


def test_theme_colors():
    """Verify Danube color tokens are properly defined."""
    assert COLOR_DANUBE_950 == "#010b18"
    assert COLOR_DANUBE_50 == "#eaf1fc"


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
        assert win.tab_archive is not None
        assert win.tab_restore is not None
        assert win.tab_execution is not None
        win.close()
