"""
Worker for running CLI processes (archive / restore / viewer) in background QThread.
Emits log lines, progress metrics, and completion events without blocking the UI.
"""

from __future__ import annotations
import os
import re
import sys
import subprocess
from typing import List, Optional
from PySide6.QtCore import QThread, Signal


class RunnerWorker(QThread):
    """Executes wab-archiver or wab-viewer in an isolated background process."""

    log_received = Signal(str, str)  # (line_text, level)
    progress_updated = Signal(int, int, str)  # (current, total, phase_text)
    stats_updated = Signal(dict)
    finished_with_code = Signal(int)

    def __init__(self, command_args: List[str], parent=None):
        super().__init__(parent)
        self.command_args = command_args
        self.process: Optional[subprocess.Popen] = None
        self._is_cancelled = False

    def run(self):
        cmd = [sys.executable] + self.command_args
        self.log_received.emit(f"Ejecutando: {' '.join(cmd)}", "DEBUG")

        try:
            # Set unbuffered output
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
            )

            current_phase = "Iniciando..."
            total_items = 0
            current_count = 0

            # Streaming line-by-line
            if self.process.stdout:
                for raw_line in iter(self.process.stdout.readline, ""):
                    if self._is_cancelled:
                        break
                    line = raw_line.strip()
                    if not line:
                        continue

                    # Classify level
                    level = "INFO"
                    if "ERROR" in line or "Error" in line:
                        level = "ERROR"
                    elif "WARNING" in line or "Warning" in line or "CONFLICT" in line:
                        level = "WARNING"
                    elif "DEBUG" in line:
                        level = "DEBUG"

                    self.log_received.emit(line, level)

                    # Simple heuristic parsing for progress
                    # e.g., "Query returned 1420 rows."
                    m_rows = re.search(r"Query returned (\d+) rows", line)
                    if m_rows:
                        total_items = int(m_rows.group(1))
                        self.progress_updated.emit(0, total_items, "Extrayendo...")

                    # e.g. "Processing..." or copy indications
                    if "Processing" in line or "Copiando" in line or "Restored" in line:
                        current_count += 1
                        if total_items > 0:
                            self.progress_updated.emit(min(current_count, total_items), total_items, "Procesando")

            self.process.wait()
            return_code = self.process.returncode if not self._is_cancelled else -1

            if self._is_cancelled:
                self.log_received.emit("Operación cancelada por el usuario.", "WARNING")
            else:
                self.log_received.emit(f"Proceso finalizado (Código: {return_code}).", "SUCCESS" if return_code == 0 else "ERROR")

            self.finished_with_code.emit(return_code)

        except Exception as e:
            self.log_received.emit(f"Fallo al ejecutar proceso: {e}", "ERROR")
            self.finished_with_code.emit(1)

    def cancel(self):
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
