"""
Non-blocking background monitor service for ADB device hotplug detection.
Tracks real-time USB connection, disconnection, authorization and device swap events.
"""

from __future__ import annotations
import time
from typing import Optional
from PySide6.QtCore import QThread, Signal

from wab_gui.services.adb_service import AdbService, DeviceInfo


class AdbDeviceMonitor(QThread):
    """Monitors ADB device state changes continuously in background."""

    device_connected = Signal(object)      # DeviceInfo
    device_disconnected = Signal(str)      # serial
    no_device_detected = Signal()
    adb_not_installed = Signal()

    def __init__(self, poll_interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self.poll_interval_ms = poll_interval_ms
        self._running = True
        self._current_serial: Optional[str] = None
        self._current_state: Optional[str] = None
        self._force_poll = False

    def stop(self):
        self._running = False
        self.quit()

    def force_poll(self):
        """Request immediate poll cycle without waiting."""
        self._force_poll = True

    def run(self):
        while self._running:
            if not AdbService.is_adb_installed():
                self.adb_not_installed.emit()
                self._current_serial = None
                self._current_state = None
                self.msleep(self.poll_interval_ms)
                continue

            try:
                devices = AdbService.list_devices()
            except Exception:
                devices = []

            active_dev: Optional[DeviceInfo] = devices[0] if devices else None

            if active_dev is None:
                # No device currently connected
                if self._current_serial is not None:
                    old_serial = self._current_serial
                    self._current_serial = None
                    self._current_state = None
                    self.device_disconnected.emit(old_serial)
                else:
                    self.no_device_detected.emit()
            else:
                # A device is plugged in
                is_new_serial = (active_dev.serial != self._current_serial)
                is_state_changed = (active_dev.state != self._current_state)

                if is_new_serial or is_state_changed or self._force_poll:
                    old_serial = self._current_serial
                    self._current_serial = active_dev.serial
                    self._current_state = active_dev.state
                    self._force_poll = False

                    if is_new_serial and old_serial is not None:
                        # Old device was unplugged or replaced
                        self.device_disconnected.emit(old_serial)

                    # Inspect device if authorized
                    if active_dev.state == "device":
                        try:
                            full_info = AdbService.inspect_device(active_dev.serial)
                        except Exception:
                            full_info = active_dev
                    else:
                        full_info = active_dev

                    self.device_connected.emit(full_info)

            # Wait for next poll interval
            sleep_chunks = max(1, self.poll_interval_ms // 100)
            for _ in range(sleep_chunks):
                if not self._running:
                    break
                if self._force_poll:
                    break
                self.msleep(100)
