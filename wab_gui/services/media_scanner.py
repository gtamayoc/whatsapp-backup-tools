"""
Service for scanning, categorizing, and analyzing WhatsApp media files
both over ADB (Android devices) and local directories.
"""

from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Callable


CATEGORY_VIDEOS = "Videos"
CATEGORY_IMAGES = "Imágenes"
CATEGORY_AUDIOS = "Audios"
CATEGORY_DOCS = "Documentos"
CATEGORY_DATABASES = "Bases de Datos"
CATEGORY_BACKUPS = "Backups / Copias"
CATEGORY_OTHER = "Otros"

EXTENSIONS = {
    CATEGORY_VIDEOS: {".mp4", ".3gp", ".mkv", ".mov", ".avi", ".webm"},
    CATEGORY_IMAGES: {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"},
    CATEGORY_AUDIOS: {".opus", ".m4a", ".mp3", ".wav", ".aac", ".ogg"},
    CATEGORY_DOCS: {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".zip", ".rar", ".7z", ".cbr", ".rtf", ".html", ".htm", ".apk"},
    CATEGORY_DATABASES: {".db", ".crypt15", ".crypt14", ".crypt12", ".sqlite", ".bak"},
    CATEGORY_BACKUPS: {".json", ".was"},
}


def should_skip_file(name: str, full_path: str) -> bool:
    """Filter out ephemeral 24h stories, temporary preview link caches, thumbnails and .nomedia."""
    lower = full_path.lower().replace("\\", "/")
    if (
        name == ".nomedia"
        or name.startswith(".")
        or "/.statuses" in lower
        or "/.links" in lower
        or "/.wamocache" in lower
        or "/.wamo" in lower
        or "/.thumbs" in lower
        or "/.stickerthumbs" in lower
        or "/.trash" in lower
        or "/.udd" in lower
        or full_path.endswith(".tmp")
    ):
        return True
    return False


def classify_file(filename: str, full_path: str = "") -> str:
    lower = full_path.lower().replace("\\", "/")

    # 1. Backups & Shared state (must be checked before generic crypt extension check)
    if "/backups/" in lower or "/.shared/" in lower or filename.startswith(("backup_settings", "status_backup", "wa.db")) or filename.endswith((".was",)):
        return CATEGORY_BACKUPS

    # 2. Databases (msgstore, databases directory, crypt files)
    if "/databases/" in lower or filename.startswith("msgstore") or filename.endswith((".crypt15", ".crypt14", ".crypt12", ".db")):
        return CATEGORY_DATABASES

    # 3. Videos
    if "/whatsapp video/" in lower or "/whatsapp video notes/" in lower or "/whatsapp animated gifs/" in lower:
        return CATEGORY_VIDEOS
    ext = os.path.splitext(filename)[1].lower()
    if ext in EXTENSIONS[CATEGORY_VIDEOS]:
        return CATEGORY_VIDEOS

    # 4. Audios & Voice notes
    if "/whatsapp voice notes/" in lower or "/whatsapp audio/" in lower:
        return CATEGORY_AUDIOS
    if ext in EXTENSIONS[CATEGORY_AUDIOS]:
        return CATEGORY_AUDIOS

    # 5. Documents (WhatsApp Documents often stores files named DOC-... without extension or ending with a dot)
    if "/whatsapp documents/" in lower or "/whatsapp document/" in lower or filename.lower().startswith("doc-"):
        return CATEGORY_DOCS
    if ext in EXTENSIONS[CATEGORY_DOCS]:
        return CATEGORY_DOCS

    # 6. Images & Stickers
    if "/whatsapp images/" in lower or "/whatsapp profile photos/" in lower or "/whatsapp stickers/" in lower or "/whatsapp sticker packs/" in lower or "/wallpaper/" in lower:
        return CATEGORY_IMAGES
    if ext in EXTENSIONS[CATEGORY_IMAGES]:
        return CATEGORY_IMAGES

    return CATEGORY_OTHER


def format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@dataclass
class MediaItem:
    name: str
    relative_path: str
    full_path: str
    size_bytes: int
    category: str
    size_formatted: str = ""

    def __post_init__(self):
        if not self.size_formatted:
            self.size_formatted = format_bytes(self.size_bytes)


@dataclass
class CategorySummary:
    name: str
    count: int = 0
    size_bytes: int = 0
    size_formatted: str = "0 B"
    percentage: float = 0.0


@dataclass
class ScanResult:
    total_files: int = 0
    total_bytes: int = 0
    total_size_formatted: str = "0 B"
    categories: Dict[str, CategorySummary] = field(default_factory=dict)
    items: List[MediaItem] = field(default_factory=list)
    source_path: str = ""
    device_name: str = "Dispositivo"


class MediaScanner:
    """Scans and analyzes WhatsApp media for storage intelligence."""

    KNOWN_DEVICE_ROOTS = [
        # Android 11+ standard
        "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp",
        # Android legacy
        "/storage/emulated/0/WhatsApp",
        # WhatsApp Business
        "/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp Business",
    ]

    @classmethod
    def get_roots_for_profile(cls, profile_id: str = "all") -> List[str]:
        roots = []
        if profile_id in ("0", "all"):
            roots.extend([
                "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp",
                "/storage/emulated/0/WhatsApp",
                "/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp Business",
            ])
        if profile_id in ("999", "all"):
            roots.extend([
                "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp",
                "/storage/emulated/999/WhatsApp",
                "/storage/emulated/999/Android/media/com.whatsapp.w4b/WhatsApp Business",
            ])
        return roots

    @classmethod
    def scan_adb_device(
        cls,
        adb_bin: str,
        serial: str,
        device_name: str,
        remote_path: Optional[str] = None,
        profile_id: str = "all",  # '0', '999', or 'all'
        progress_cb: Optional[Callable[[str], None]] = None,
        db_path: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ScanResult:
        import time
        from wab_gui.services.scan_db import ScanDatabase

        db = ScanDatabase(db_path)
        if not session_id:
            clean_sn = "".join(c for c in serial if c.isalnum() or c in ("-", "_")) or "device"
            session_id = f"{clean_sn}_{int(time.time())}"

        db.create_session(
            session_id=session_id,
            device_serial=serial,
            device_name=device_name,
            profile_id=profile_id,
            source_path=remote_path or f"WhatsApp ({profile_id})"
        )

        result = ScanResult(
            source_path=remote_path or f"WhatsApp ({profile_id})",
            device_name=device_name
        )
        result.session_id = session_id
        result.db_path = db.db_path

        categories = {
            CATEGORY_VIDEOS: CategorySummary(name=CATEGORY_VIDEOS),
            CATEGORY_IMAGES: CategorySummary(name=CATEGORY_IMAGES),
            CATEGORY_AUDIOS: CategorySummary(name=CATEGORY_AUDIOS),
            CATEGORY_DOCS: CategorySummary(name=CATEGORY_DOCS),
            CATEGORY_DATABASES: CategorySummary(name=CATEGORY_DATABASES),
            CATEGORY_BACKUPS: CategorySummary(name=CATEGORY_BACKUPS),
            CATEGORY_OTHER: CategorySummary(name=CATEGORY_OTHER),
        }

        roots_to_scan = [remote_path] if remote_path else cls.get_roots_for_profile(profile_id)

        total_bytes = 0
        total_files = 0
        visited_paths = set()
        batch_rows = []
        last_cb_time = time.time()

        for root in roots_to_scan:
            if progress_cb:
                progress_cb(f"Escaneando {os.path.basename(root)}...")

            # Fast toybox find -printf (streamed line by line)
            cmd = [
                adb_bin, "-s", serial, "shell",
                f"find '{root}' -type f -printf '%s %p\\n' 2>/dev/null"
            ]

            lines_found = 0
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    errors="replace",
                    bufsize=65536
                )
                if proc and proc.stdout:
                    for line in proc.stdout:
                        line = line.strip()
                        if not line or " " not in line:
                            continue
                        parts = line.split(" ", 1)
                        try:
                            size = int(parts[0])
                            full_path = parts[1].strip()
                        except ValueError:
                            continue

                        lines_found += 1
                        if full_path in visited_paths:
                            continue
                        visited_paths.add(full_path)

                        name = os.path.basename(full_path)
                        if should_skip_file(name, full_path):
                            continue

                        rel_path = full_path
                        if full_path.startswith(root):
                            rel_path = full_path[len(root):].lstrip("/\\")

                        cat = classify_file(name, full_path)
                        ext = os.path.splitext(name)[1].lower()

                        batch_rows.append((name, rel_path, full_path, size, cat, ext, 0))
                        total_bytes += size
                        total_files += 1

                        if len(batch_rows) >= 2000:
                            db.insert_files_batch(session_id, serial, batch_rows)
                            batch_rows.clear()
                            now = time.time()
                            if progress_cb and (now - last_cb_time >= 0.4):
                                progress_cb(
                                    f"Escaneando {os.path.basename(root)}... {total_files:,} archivos ({format_bytes(total_bytes)})"
                                )
                                last_cb_time = now

                    proc.wait(timeout=5)
            except Exception:
                pass

            # Fallback if find -printf returned nothing
            if lines_found == 0:
                fallback_cmd = [
                    adb_bin, "-s", serial, "shell",
                    f"find '{root}' -type f ! -name '.*' -exec stat -c '%s %n' {{}} + 2>/dev/null"
                ]
                try:
                    fproc = subprocess.Popen(
                        fallback_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        errors="replace",
                        bufsize=65536
                    )
                    if fproc and fproc.stdout:
                        for line in fproc.stdout:
                            line = line.strip()
                            if not line or " " not in line:
                                continue
                            parts = line.split(" ", 1)
                            try:
                                size = int(parts[0])
                                full_path = parts[1].strip()
                            except ValueError:
                                continue

                            if full_path in visited_paths:
                                continue
                            visited_paths.add(full_path)

                            name = os.path.basename(full_path)
                            if should_skip_file(name, full_path):
                                continue

                            rel_path = full_path
                            if full_path.startswith(root):
                                rel_path = full_path[len(root):].lstrip("/\\")

                            cat = classify_file(name, full_path)
                            ext = os.path.splitext(name)[1].lower()

                            batch_rows.append((name, rel_path, full_path, size, cat, ext, 0))
                            total_bytes += size
                            total_files += 1

                            if len(batch_rows) >= 2000:
                                db.insert_files_batch(session_id, serial, batch_rows)
                                batch_rows.clear()
                                now = time.time()
                                if progress_cb and (now - last_cb_time >= 0.4):
                                    progress_cb(
                                        f"Escaneando {os.path.basename(root)}... {total_files:,} archivos ({format_bytes(total_bytes)})"
                                    )
                                    last_cb_time = now

                        fproc.wait(timeout=5)
                except Exception:
                    pass

        if batch_rows:
            db.insert_files_batch(session_id, serial, batch_rows)
            batch_rows.clear()

        db.finalize_session(session_id)
        breakdown = db.get_category_breakdown(session_id)
        for cat_name, cat_data in breakdown.items():
            if cat_name in categories:
                categories[cat_name].count = cat_data["count"]
                categories[cat_name].size_bytes = cat_data["size_bytes"]
                categories[cat_name].size_formatted = cat_data["size_formatted"]
                categories[cat_name].percentage = cat_data["percentage"]

        result.total_files = total_files
        result.total_bytes = total_bytes
        result.total_size_formatted = format_bytes(total_bytes)
        result.categories = categories

        # Populate sample items for backward compatibility (first 500)
        sample_db_items = db.query_files(session_id, limit=500)
        result.items = [
            MediaItem(
                name=it.name,
                relative_path=it.relative_path,
                full_path=it.full_path,
                size_bytes=it.size_bytes,
                category=it.category,
                size_formatted=it.size_formatted
            )
            for it in sample_db_items
        ]
        return result

    @classmethod
    def scan_local_folder(
        cls,
        folder_path: str,
        device_name: str = "Local",
        progress_cb: Optional[Callable[[str], None]] = None,
        db_path: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ScanResult:
        import time
        from wab_gui.services.scan_db import ScanDatabase

        db = ScanDatabase(db_path)
        if not session_id:
            clean_dn = "".join(c for c in device_name if c.isalnum() or c in ("-", "_")) or "local"
            session_id = f"{clean_dn}_{int(time.time())}"

        db.create_session(
            session_id=session_id,
            device_serial=device_name,
            device_name=device_name,
            profile_id="local",
            source_path=folder_path
        )

        result = ScanResult(source_path=folder_path, device_name=device_name)
        result.session_id = session_id
        result.db_path = db.db_path

        categories = {
            CATEGORY_VIDEOS: CategorySummary(name=CATEGORY_VIDEOS),
            CATEGORY_IMAGES: CategorySummary(name=CATEGORY_IMAGES),
            CATEGORY_AUDIOS: CategorySummary(name=CATEGORY_AUDIOS),
            CATEGORY_DOCS: CategorySummary(name=CATEGORY_DOCS),
            CATEGORY_DATABASES: CategorySummary(name=CATEGORY_DATABASES),
            CATEGORY_BACKUPS: CategorySummary(name=CATEGORY_BACKUPS),
            CATEGORY_OTHER: CategorySummary(name=CATEGORY_OTHER),
        }

        root_p = Path(folder_path)
        if not root_p.exists():
            return result

        batch_rows = []
        total_bytes = 0
        total_files = 0
        last_cb_time = time.time()

        for file_p in root_p.rglob("*"):
            if not file_p.is_file():
                continue
            name = file_p.name
            full_str = str(file_p)
            if should_skip_file(name, full_str):
                continue

            try:
                size = file_p.stat().st_size
                mtime = int(file_p.stat().st_mtime)
            except OSError:
                size = 0
                mtime = 0

            rel_path = str(file_p.relative_to(root_p)).replace("\\", "/")
            cat = classify_file(name, full_str)
            ext = os.path.splitext(name)[1].lower()

            batch_rows.append((name, rel_path, full_str.replace("\\", "/"), size, cat, ext, mtime))
            total_bytes += size
            total_files += 1

            if len(batch_rows) >= 2000:
                db.insert_files_batch(session_id, device_name, batch_rows)
                batch_rows.clear()
                now = time.time()
                if progress_cb and (now - last_cb_time >= 0.4):
                    progress_cb(f"Escaneando archivos locales... {total_files:,} archivos ({format_bytes(total_bytes)})")
                    last_cb_time = now

        if batch_rows:
            db.insert_files_batch(session_id, device_name, batch_rows)
            batch_rows.clear()

        db.finalize_session(session_id)
        breakdown = db.get_category_breakdown(session_id)
        for cat_name, cat_data in breakdown.items():
            if cat_name in categories:
                categories[cat_name].count = cat_data["count"]
                categories[cat_name].size_bytes = cat_data["size_bytes"]
                categories[cat_name].size_formatted = cat_data["size_formatted"]
                categories[cat_name].percentage = cat_data["percentage"]

        result.total_files = total_files
        result.total_bytes = total_bytes
        result.total_size_formatted = format_bytes(total_bytes)
        result.categories = categories

        sample_db_items = db.query_files(session_id, limit=500)
        result.items = [
            MediaItem(
                name=it.name,
                relative_path=it.relative_path,
                full_path=it.full_path,
                size_bytes=it.size_bytes,
                category=it.category,
                size_formatted=it.size_formatted
            )
            for it in sample_db_items
        ]
        return result
