"""
Services for ADB inspection, device detection, battery, storage and WhatsApp path checking.
100% root-free, using safe Android shell and property queries.
"""

from __future__ import annotations
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from wab_gui.services.adb_installer import AdbInstaller


@dataclass
class DeviceInfo:
    serial: str
    state: str  # 'device', 'unauthorized', 'offline', 'no_permissions'
    model: str = "Desconocido"
    manufacturer: str = "Desconocido"
    android_version: str = "N/A"
    sdk_level: str = "N/A"
    battery_level: Optional[int] = None
    is_charging: bool = False
    storage_total: str = "N/A"
    storage_used: str = "N/A"
    storage_free: str = "N/A"
    storage_percent: Optional[int] = None
    whatsapp_paths: Dict[str, bool] = field(default_factory=dict)
    has_msgstore_crypt: bool = False
    msgstore_size_mb: Optional[float] = None
    profiles: List[Dict[str, str]] = field(default_factory=list)  # [{'id': '0', 'name': 'Principal'}, {'id': '999', 'name': 'MultiApp'}]


class AdbService:
    """Non-invasive inspection service for Android devices over ADB."""

    KNOWN_WA_LOCATIONS = {
        "WhatsApp Media (Android 11+)": "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media",
        "WhatsApp Databases (Android 11+)": "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases",
        "WhatsApp Legacy Media": "/storage/emulated/0/WhatsApp/Media",
        "WhatsApp Legacy Databases": "/storage/emulated/0/WhatsApp/Databases",
        "WhatsApp Business Media": "/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp Business/Media",
        "WhatsApp Business Databases": "/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp Business/Databases",
    }

    @staticmethod
    def get_adb_path() -> Optional[str]:
        return AdbInstaller.find_adb()

    @staticmethod
    def is_adb_installed() -> bool:
        return AdbInstaller.find_adb() is not None

    @classmethod
    def list_devices(cls) -> List[DeviceInfo]:
        """List all connected devices and their authorization status."""
        adb_bin = cls.get_adb_path()
        if not adb_bin:
            return []

        try:
            res = subprocess.run(
                [adb_bin, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                return []
        except Exception:
            return []

        devices: List[DeviceInfo] = []
        lines = res.stdout.strip().splitlines()
        for line in lines[1:]:  # Skip 'List of devices attached' header
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                dev = DeviceInfo(serial=serial, state=state)
                devices.append(dev)

        return devices

    @classmethod
    def inspect_device(cls, serial: str) -> DeviceInfo:
        """Fetch detailed hardware, battery, storage, and WhatsApp metadata for an authorized device."""
        dev = DeviceInfo(serial=serial, state="device")

        # Basic device properties
        props = cls._get_properties(serial)
        dev.model = props.get("ro.product.model", props.get("ro.product.device", "Android Device"))
        dev.manufacturer = props.get("ro.product.manufacturer", "Desconocido").capitalize()
        dev.android_version = props.get("ro.build.version.release", "N/A")
        dev.sdk_level = props.get("ro.build.version.sdk", "N/A")

        # Battery status
        battery = cls._get_battery(serial)
        dev.battery_level = battery.get("level")
        dev.is_charging = battery.get("charging", False)

        # Storage
        storage = cls._get_storage(serial)
        dev.storage_total = storage.get("total", "N/A")
        dev.storage_used = storage.get("used", "N/A")
        dev.storage_free = storage.get("free", "N/A")
        dev.storage_percent = storage.get("percent")

        # WhatsApp paths check (safe non-root)
        wa_paths = {}
        for name, remote_path in cls.KNOWN_WA_LOCATIONS.items():
            wa_paths[name] = cls._path_exists(serial, remote_path)
        dev.whatsapp_paths = wa_paths

        # Check msgstore.db.crypt15
        standard_crypt = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15"
        legacy_crypt = "/storage/emulated/0/WhatsApp/Databases/msgstore.db.crypt15"
        dev.has_msgstore_crypt = cls._path_exists(serial, standard_crypt) or cls._path_exists(serial, legacy_crypt)

        # Android user profiles (Dual App / MultiApp / Cloned spaces)
        dev.profiles = cls._get_profiles(serial)

        return dev

    @classmethod
    def _run_cmd(cls, serial: str, cmd_args: List[str], timeout: int = 5) -> str:
        try:
            adb_bin = cls.get_adb_path() or "adb"
            full_cmd = [adb_bin, "-s", serial] + cmd_args
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return res.stdout.strip()
        except Exception:
            return ""

    @classmethod
    def _get_properties(cls, serial: str) -> Dict[str, str]:
        out = cls._run_cmd(serial, ["shell", "getprop"])
        props = {}
        for line in out.splitlines():
            if ":" in line and line.startswith("[") and line.endswith("]"):
                try:
                    k, v = line.split("]: [", 1)
                    key = k.strip("[")
                    val = v.rstrip("]")
                    props[key] = val
                except ValueError:
                    continue
        return props

    @classmethod
    def _get_battery(cls, serial: str) -> Dict[str, any]:
        out = cls._run_cmd(serial, ["shell", "dumpsys", "battery"])
        info = {"level": None, "charging": False}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("level:"):
                try:
                    info["level"] = int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("status:"):
                # 2 = Charging, 5 = Full
                status_val = line.split(":")[1].strip()
                info["charging"] = status_val in ("2", "5")
        return info

    @classmethod
    def _get_storage(cls, serial: str) -> Dict[str, any]:
        out = cls._run_cmd(serial, ["shell", "df", "-h", "/storage/emulated/0"])
        info = {"total": "N/A", "used": "N/A", "free": "N/A", "percent": None}
        lines = out.splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            # Standard df output: Filesystem Size Used Avail Use% Mounted on
            if len(parts) >= 5:
                info["total"] = parts[1]
                info["used"] = parts[2]
                info["free"] = parts[3]
                try:
                    pct_str = parts[4].replace("%", "")
                    info["percent"] = int(pct_str)
                except ValueError:
                    pass
        return info

    @classmethod
    def _path_exists(cls, serial: str, remote_path: str) -> bool:
        out = cls._run_cmd(serial, ["shell", f"ls -d '{remote_path}' 2>/dev/null"])
        return len(out) > 0 and "No such file" not in out

    @classmethod
    def _get_profiles(cls, serial: str) -> List[Dict[str, str]]:
        """Parse user profiles via 'pm list users' (e.g. 0:Owner, 999:MultiApp)."""
        out = cls._run_cmd(serial, ["shell", "pm list users"])
        profiles = []
        import re
        for line in out.splitlines():
            # UserInfo{0:Propietario:4c13} or UserInfo{999:MultiApp:4001010}
            m = re.search(r"UserInfo\{(\d+):([^:]+):", line)
            if m:
                u_id = m.group(1)
                u_name = m.group(2).strip()
                profiles.append({"id": u_id, "name": u_name})
        if not profiles:
            profiles.append({"id": "0", "name": "Principal"})
        return profiles
