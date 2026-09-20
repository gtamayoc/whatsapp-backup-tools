"""
Direct extractor service to pull or copy media into results/[device]/
preserving original relative folder structure without artificial subcategory partitioning.
"""

from __future__ import annotations
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from wab_gui.services.media_scanner import MediaItem


class DirectExtractorWorker(QThread):
    """Worker to extract files directly to results/[device]/ with progress."""

    progress_sig = Signal(int, int, str)  # (current, total, current_filename)
    log_sig = Signal(str, str)            # (message, level)
    finished_sig = Signal(bool, str, int) # (success, destination_folder, extracted_count)

    def __init__(
        self,
        items: List[MediaItem],
        device_name: str,
        adb_bin: Optional[str] = None,
        serial: Optional[str] = None,
        base_results_dir: str = "results",
        parent=None,
    ):
        super().__init__(parent)
        self.items = items
        self.device_name = "".join(c for c in device_name if c.isalnum() or c in ("-", "_")).strip() or "dispositivo"
        self.adb_bin = adb_bin
        self.serial = serial
        self.base_results_dir = base_results_dir
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        target_dir = Path(self.base_results_dir) / self.device_name
        target_dir.mkdir(parents=True, exist_ok=True)

        total = len(self.items)
        extracted = 0

        self.log_sig.emit(f"Iniciando extracción de {total} archivos hacia: {target_dir}", "INFO")

        # Case 1: ADB extraction
        if self.adb_bin and self.serial:
            for i, item in enumerate(self.items, 1):
                if self._is_cancelled:
                    self.log_sig.emit("Extracción cancelada por el usuario.", "WARNING")
                    self.finished_sig.emit(False, str(target_dir), extracted)
                    return

                # Local destination preserving relative path inside WhatsApp/Media
                dest_file = target_dir / item.relative_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                self.progress_sig.emit(i, total, item.name)

                # Skip identical if already exists and same size
                if dest_file.exists() and dest_file.stat().st_size == item.size_bytes:
                    extracted += 1
                    continue

                cmd = [self.adb_bin, "-s", self.serial, "pull", item.full_path, str(dest_file)]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=120, check=True)
                    extracted += 1
                except Exception as e:
                    self.log_sig.emit(f"Error al extraer {item.name}: {e}", "ERROR")

        # Case 2: Local folder copy
        else:
            for i, item in enumerate(self.items, 1):
                if self._is_cancelled:
                    self.log_sig.emit("Extracción cancelada por el usuario.", "WARNING")
                    self.finished_sig.emit(False, str(target_dir), extracted)
                    return

                dest_file = target_dir / item.relative_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                self.progress_sig.emit(i, total, item.name)

                if dest_file.exists() and dest_file.stat().st_size == item.size_bytes:
                    extracted += 1
                    continue

                try:
                    shutil.copy2(item.full_path, dest_file)
                    extracted += 1
                except Exception as e:
                    self.log_sig.emit(f"Error al copiar {item.name}: {e}", "ERROR")

        self.log_sig.emit(f"✓ Extracción finalizada con éxito. {extracted} archivos en: {target_dir}", "SUCCESS")
        self.finished_sig.emit(True, str(target_dir), extracted)
