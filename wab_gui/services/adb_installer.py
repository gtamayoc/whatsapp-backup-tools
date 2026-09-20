"""
Service to automatically download, unpack, configure, and manage Android Platform Tools (ADB).
Allows automatic installation into local user appdata / project tool cache, and optionally adding to PATH.
"""

from __future__ import annotations
import os
import sys
import shutil
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional, Callable


PLATFORM_TOOLS_URLS = {
    "win32": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
    "linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
}


def get_default_adb_dir() -> Path:
    """Return persistent local directory where platform-tools is installed."""
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            base = Path(local_appdata) / "Android" / "platform-tools"
            return base
    return Path.home() / ".android-platform-tools" / "platform-tools"


class AdbInstaller:
    """Handles downloading and setup of official Android platform-tools."""

    @classmethod
    def find_adb(cls) -> Optional[str]:
        """Look for adb in PATH, common SDK locations, or our local install directory."""
        # 1. System PATH
        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb

        # 2. Local AppData / Managed directory
        local_dir = get_default_adb_dir()
        binary_name = "adb.exe" if sys.platform == "win32" else "adb"
        candidate = local_dir / binary_name
        if candidate.is_file():
            cls.add_to_runtime_path(str(local_dir))
            return str(candidate)

        # 3. Standard Android SDK locations
        if sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            sdk_candidates = [
                Path(local_appdata) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
                Path("C:/Android/platform-tools/adb.exe"),
                Path("C:/platform-tools/adb.exe"),
            ]
            for c in sdk_candidates:
                if c.is_file():
                    cls.add_to_runtime_path(str(c.parent))
                    return str(c)

        return None

    @classmethod
    def add_to_runtime_path(cls, folder_path: str):
        """Add folder to current process PATH and os.environ."""
        norm = os.path.normpath(folder_path)
        paths = os.environ.get("PATH", "").split(os.pathsep)
        if norm not in [os.path.normpath(p) for p in paths]:
            os.environ["PATH"] = norm + os.pathsep + os.environ.get("PATH", "")

    @classmethod
    def add_to_user_path_windows(cls, folder_path: str) -> bool:
        """Permanently add directory to Windows User PATH via registry."""
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            )
            try:
                current_path, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path = ""

            norm_target = os.path.normpath(folder_path)
            parts = [p.strip() for p in current_path.split(";") if p.strip()]
            if norm_target not in [os.path.normpath(p) for p in parts]:
                parts.append(norm_target)
                new_path = ";".join(parts)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                winreg.CloseKey(key)

                # Broadcast WM_SETTINGCHANGE so new terminals notice it
                try:
                    import ctypes
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    result = ctypes.c_ulong()
                    ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                        SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
                    )
                except Exception:
                    pass
                return True
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    @classmethod
    def download_and_install_adb(
        cls,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Optional[str]:
        """
        Download official Android platform-tools zip from Google,
        extract into user directory and register in runtime and user PATH.
        """
        target_platform = "win32" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
        url = PLATFORM_TOOLS_URLS.get(target_platform)
        if not url:
            if progress_callback:
                progress_callback(0, f"Plataforma {sys.platform} no soportada para descarga automática.")
            return None

        dest_folder = get_default_adb_dir()
        parent_dir = dest_folder.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        zip_path = parent_dir / "platform-tools.zip"

        if progress_callback:
            progress_callback(10, "Descargando Android Platform-Tools desde Google...")

        try:
            # Download with progress
            def reporthook(block_num, block_size, total_size):
                if total_size > 0 and progress_callback:
                    pct = min(int((block_num * block_size / total_size) * 60) + 10, 70)
                    progress_callback(pct, f"Descargando ADB ({pct}%)...")

            urllib.request.urlretrieve(url, zip_path, reporthook=reporthook)

            if progress_callback:
                progress_callback(75, "Extrayendo archivos de Platform-Tools...")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(parent_dir)

            try:
                zip_path.unlink()
            except Exception:
                pass

            binary_name = "adb.exe" if sys.platform == "win32" else "adb"
            adb_bin = dest_folder / binary_name

            if adb_bin.is_file():
                # Make executable on unix
                if sys.platform != "win32":
                    adb_bin.chmod(0o755)

                cls.add_to_runtime_path(str(dest_folder))
                if sys.platform == "win32":
                    cls.add_to_user_path_windows(str(dest_folder))

                if progress_callback:
                    progress_callback(100, f"ADB instalado correctamente en: {dest_folder}")
                return str(adb_bin)
            else:
                if progress_callback:
                    progress_callback(0, "Error: No se encontró el ejecutable tras la descompresión.")
                return None

        except Exception as e:
            if progress_callback:
                progress_callback(0, f"Error durante la instalación: {e}")
            return None
