import csv
import datetime
import os
import posixpath
import shutil
import sqlite3
import subprocess
import time
import logging

from shared.hashing import file_md5
from shared.source_detection import WA_DATABASES_DIR_NAME

# Standard WhatsApp paths (Scoped Storage, Android 11+)
_MSGSTORE_PATH = (
    '/storage/emulated/0/Android/media/com.whatsapp'
    '/WhatsApp/Databases/msgstore.db.crypt15'
)
_MSGSTORE_BUSINESS_PATH = (
    '/storage/emulated/0/Android/media/com.whatsapp.w4b'
    '/WhatsApp Business/Databases/msgstore.db.crypt15'
)
_WA_MEDIA_ROOT = '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media'
_WA_BUSINESS_MEDIA_ROOT = (
    '/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp Business/Media'
)

# Legacy paths (Android 10 and below)
_WA_LEGACY_ROOT = '/storage/emulated/0/WhatsApp'
_WA_BUSINESS_LEGACY_ROOT = '/storage/emulated/0/WhatsApp Business'

_CONTACTS_URI = 'content://com.android.contacts/data'
_CONTACTS_PROJECTION = 'display_name:data1'

_TRANSIENT_ERRORS = (
    'error: closed',
    'Connection reset by peer',
    'Broken pipe',
    'device offline',
)
_ADB_TIMEOUT = 120  # seconds per adb call; WiFi ADB can hang silently
_ADB_RETRIES = 2

_PROTECTED_EXTENSIONS = frozenset({
    '.db', '.db-wal', '.db-shm',
    '.sqlite', '.sqlite-wal', '.sqlite-shm',
    '.crypt12', '.crypt14', '.crypt15',
    '.key', '.toml', '.log', '.csv', '.json', '.xml',
})

_PROTECTED_NAMES = frozenset({
    'msgstore', 'wa.db', 'chatstorage', 'key',
    '.wa_media_archiver.db', '.wa_viewer.db',
})

_PROTECTED_DIR_PARTS = frozenset({
    'databases', 'backups', 'shared', 'trash',
})


def is_protected_remote_file(remote_path: str) -> bool:
    """Strictly protect databases, keys, and backups from deletion on the device."""
    lower = remote_path.lower().replace('\\', '/')
    filename = posixpath.basename(lower)
    _, ext = posixpath.splitext(filename)

    if ext in _PROTECTED_EXTENSIONS:
        return True
    for protected in _PROTECTED_NAMES:
        if protected in filename:
            return True
    parts = set(lower.split('/'))
    if parts.intersection(_PROTECTED_DIR_PARTS):
        return True
    return False


def check_adb(logger=None) -> bool:
    if shutil.which('adb'):
        return True
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local_appdata, "Android", "Sdk", "platform-tools"),
        os.path.join(os.path.expanduser("~"), ".android-platform-tools", "platform-tools"),
        "C:\\Android\\platform-tools",
        "C:\\platform-tools",
    ]
    for c in candidates:
        adb_file = os.path.join(c, "adb.exe" if os.name == 'nt' else "adb")
        if os.path.isfile(adb_file):
            os.environ["PATH"] = c + os.pathsep + os.environ.get("PATH", "")
            if shutil.which('adb'):
                return True
    if logger:
        logger.error(
            "ADB not found on PATH. Install Android SDK Platform Tools and add it to your PATH.\n"
            "  Download: https://developer.android.com/tools/releases/platform-tools"
        )
    return False


def check_device_connected(logger=None) -> bool:
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if logger:
            stderr = e.stderr.decode(errors='replace').strip() if hasattr(e, 'stderr') else str(e)
            logger.error(f"'adb devices' failed: {stderr}")
        return False

    lines = result.stdout.decode(errors='replace').splitlines()
    connected = [line for line in lines if line.strip().endswith('device')]
    if connected:
        return True

    if logger:
        logger.error(
            "No Android device detected. Ensure:\n"
            "  1. USB debugging is enabled on the device (Settings > Developer options)\n"
            "  2. The device is connected via USB\n"
            "  3. You have authorised the connection on the phone when prompted"
        )
    return False


def _run_adb(cmd: list, logger=None) -> subprocess.CompletedProcess:
    """Run an ADB command with retries on transient connection errors."""
    last_exc = None
    for attempt in range(_ADB_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=_ADB_TIMEOUT,
            )
            if result.returncode == 0:
                return result
            stderr = result.stderr.decode(errors='replace')
            if any(e in stderr for e in _TRANSIENT_ERRORS):
                if attempt < _ADB_RETRIES:
                    if logger:
                        logger.warning(
                            f"Transient ADB error (attempt {attempt + 1}/{_ADB_RETRIES + 1}): "
                            f"{stderr.strip()}"
                        )
                    time.sleep(2)
                    continue
            raise subprocess.CalledProcessError(result.returncode, cmd,
                                                result.stdout, result.stderr)
        except subprocess.TimeoutExpired as e:
            last_exc = e
            if attempt < _ADB_RETRIES:
                if logger:
                    logger.warning(
                        f"ADB command timed out (attempt {attempt + 1}/{_ADB_RETRIES + 1}), "
                        f"retrying..."
                    )
                time.sleep(2)
                continue
            raise RuntimeError(
                f"ADB command timed out after {_ADB_RETRIES + 1} attempts: {' '.join(cmd)}"
            ) from last_exc
    raise subprocess.CalledProcessError(1, cmd)


def detect_device_whatsapp_paths(business: bool = False, logger=None) -> dict:
    """
    Detect whether WhatsApp on the device is in Scoped Storage (Android 11+)
    or legacy storage, and locate the active Databases/ and Media/ folders.
    """
    if business:
        candidates = [
            ('/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp Business', True),
            (_WA_BUSINESS_LEGACY_ROOT, False),
            ('/sdcard/WhatsApp Business', False),
        ]
    else:
        candidates = [
            ('/storage/emulated/0/Android/media/com.whatsapp/WhatsApp', True),
            (_WA_LEGACY_ROOT, False),
            ('/sdcard/WhatsApp', False),
        ]

    for root, is_scoped in candidates:
        try:
            res = _run_adb(['adb', 'shell', f'[ -d "{root}" ] && echo "FOUND"'], logger)
            if 'FOUND' in res.stdout.decode(errors='replace'):
                if logger:
                    logger.info(f"Detected WhatsApp root on device ({'Scoped Storage' if is_scoped else 'Legacy'}): {root}")
                return {
                    'whatsapp_root': root,
                    'media_root': f"{root}/Media",
                    'databases_root': f"{root}/Databases",
                    'is_scoped': is_scoped,
                    'exists': True,
                }
        except Exception:
            pass

    default_root = candidates[0][0]
    if logger:
        logger.debug(f"Using default target WhatsApp root on device: {default_root}")
    return {
        'whatsapp_root': default_root,
        'media_root': f"{default_root}/Media",
        'databases_root': f"{default_root}/Databases",
        'is_scoped': candidates[0][1],
        'exists': False,
    }


def pull_msgstore(output_dir: str, business: bool = False, logger=None) -> str:
    paths = detect_device_whatsapp_paths(business, logger)
    db_dir = paths['databases_root']

    # Locate the newest msgstore.db.crypt* on device
    remote = None
    try:
        res = _run_adb(['adb', 'shell', f'ls -1t "{db_dir}"/msgstore.db.crypt* 2>/dev/null'], logger)
        lines = [line.strip() for line in res.stdout.decode(errors='replace').splitlines() if line.strip()]
        if lines:
            remote = lines[0]
    except Exception:
        pass

    if not remote:
        remote = _MSGSTORE_BUSINESS_PATH if business else _MSGSTORE_PATH

    fname = posixpath.basename(remote)
    dest = os.path.join(output_dir, fname)
    if logger:
        logger.info(f"Pulling msgstore backup via ADB from {remote}...")
    try:
        subprocess.run(
            ['adb', 'pull', remote, dest],
            check=True, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        if logger:
            logger.error(
                f"ADB pull failed.\n"
                f"  {e.stderr.decode(errors='replace').strip()}\n"
                f"  Make sure the device is connected, USB debugging is enabled, "
                f"and the connection is authorised on the phone."
            )
        raise
    return dest


def pull_contacts(output_dir: str, logger=None) -> str:
    dest = os.path.join(output_dir, 'wa_contacts')
    if logger:
        logger.info("Pulling contacts via ADB...")
    try:
        result = subprocess.run(
            ['adb', 'shell', 'content', 'query',
             '--uri', _CONTACTS_URI,
             '--projection', _CONTACTS_PROJECTION],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
    except subprocess.CalledProcessError as e:
        if logger:
            logger.error(
                f"ADB contacts query failed.\n"
                f"  {e.stderr.decode(errors='replace').strip()}"
            )
        raise

    lines = result.stdout.decode(errors='replace').splitlines()
    wa_lines = [line for line in lines if '@s.whatsapp.net' in line]
    with open(dest, 'w', encoding='utf-8') as f:
        f.write('\n'.join(wa_lines) + '\n')
    return dest


def get_device_serial(logger=None) -> str:
    """Return the serial number of the connected ADB device."""
    result = subprocess.run(
        ['adb', 'get-serialno'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=_ADB_TIMEOUT,
    )
    serial = result.stdout.decode(errors='replace').strip()
    if result.returncode != 0 or not serial or serial == 'unknown':
        raise RuntimeError(
            f"Could not get device serial: {result.stderr.decode(errors='replace').strip()}"
        )
    if logger:
        logger.debug(f"Device serial: {serial}")
    return serial


def probe_md5_binary(logger=None) -> str:
    """Return the name of the md5 binary available on the device ('md5sum' or 'md5')."""
    result = subprocess.run(
        ['adb', 'shell', 'which md5sum || which md5'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=_ADB_TIMEOUT,
    )
    path = result.stdout.decode(errors='replace').strip().splitlines()
    if not path or result.returncode == 127:
        raise RuntimeError(
            "Neither md5sum nor md5 found on device — "
            "cannot verify file hashes for ADB."
        )
    binary = os.path.basename(path[0])
    if logger:
        logger.debug(f"md5 binary on device: {binary}")
    return binary


def _classify_adb_error(stderr: str) -> str:
    """Return a human-readable explanation of an ADB failure."""
    if 'does not exist' in stderr:
        return "Remote path not found"
    if 'Permission denied' in stderr or 'open failed' in stderr:
        return "Permission denied — file not accessible without root"
    if 'device not found' in stderr or 'device offline' in stderr:
        return "Device disconnected or offline"
    if 'No space left on device' in stderr:
        return "Host disk is full"
    return stderr.strip()


def enumerate_remote_files(wa_media_root: str, logger=None) -> list:
    """Return list of (remote_path, size_bytes) for all files under wa_media_root."""
    if logger:
        logger.info(f"Enumerating remote files under {wa_media_root}...")
    result = _run_adb(
        ['adb', 'shell', f'find "{wa_media_root}" -type f -printf "%p\\t%s\\n"'],
        logger,
    )
    entries = []
    for line in result.stdout.decode(errors='replace').splitlines():
        line = line.strip()
        if not line:
            continue
        if 'Permission denied' in line or 'No such file or directory' in line:
            if logger:
                logger.debug(f"find: skipped inaccessible path: {line}")
            continue
        parts = line.rsplit('\t', 1)
        if len(parts) != 2:
            continue
        remote_path, size_str = parts
        try:
            entries.append((remote_path.strip(), int(size_str.strip())))
        except ValueError:
            if logger:
                logger.debug(f"find: could not parse size in line: {line!r}")
    if logger:
        logger.info(f"Found {len(entries)} files on device.")
    return entries


def _remote_md5(remote_path: str, md5_binary: str, logger=None) -> bytes:
    """Return the MD5 hash of a remote file as bytes."""
    result = _run_adb(
        ['adb', 'shell', f'{md5_binary} "{remote_path}"'],
        logger,
    )
    out = result.stdout.decode(errors='replace').strip()
    if ':' in out and not out.startswith('/'):
        hex_str = out.split(':', 1)[1].strip()
    else:
        hex_str = out.split()[0]
    return bytes.fromhex(hex_str)


def _staging_path(remote_path: str, remote_root: str, staging_dir: str) -> str:
    """Map a remote absolute path to a local staging path."""
    rel = remote_path[len(remote_root):].lstrip('/')
    return os.path.join(staging_dir, rel.replace('/', os.sep))


def pull_media(staging_dir: str, business: bool,
               conn: sqlite3.Connection, logger) -> tuple:
    """
    Pull WhatsApp media from a connected device to staging_dir.
    """
    from . import archive_db as _arc

    paths = detect_device_whatsapp_paths(business, logger)
    wa_media_root = paths['media_root']
    os.makedirs(staging_dir, exist_ok=True)

    device_serial = get_device_serial(logger)
    md5_binary = probe_md5_binary(logger)

    partial_paths = _arc.get_adb_partial_paths(conn, device_serial)
    if partial_paths:
        logger.info(f"Cleaning {len(partial_paths)} partial file(s) from previous run...")
    for remote_path in partial_paths:
        local = _staging_path(remote_path, wa_media_root, staging_dir)
        if os.path.exists(local):
            os.remove(local)
            logger.debug(f"Removed partial: {local}")
        _arc.remove_adb_pull_state(conn, remote_path, device_serial)

    filename_index = _arc.build_archive_filename_index(conn)
    remote_files = enumerate_remote_files(wa_media_root, logger)
    if not remote_files:
        logger.warning("No media files found on device.")
        return 0, 0, []

    logger.info(
        f"Found {len(remote_files):,} file(s) to evaluate. "
        "If your WhatsApp media folder is several gigabytes, this can take time..."
    )

    done_paths = _arc.get_adb_done_paths(conn, device_serial)

    pull_list = []
    skip_count = 0
    conflicts = []

    for remote_path, remote_size in remote_files:
        if remote_path in done_paths:
            skip_count += 1
            continue
        basename = os.path.basename(remote_path)
        if basename not in filename_index:
            pull_list.append((remote_path, remote_size))
            continue
        db_size, db_md5 = filename_index[basename]
        if db_size is not None and db_size != remote_size:
            pull_list.append((remote_path, remote_size))
            continue
        try:
            remote_md5 = _remote_md5(remote_path, md5_binary, logger)
        except Exception as e:
            logger.warning(f"Could not hash remote file {remote_path}: {e} — will pull")
            pull_list.append((remote_path, remote_size))
            continue
        if remote_md5 == db_md5:
            skip_count += 1
            _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'done')
        else:
            conflicts.append({
                'remote_path': remote_path,
                'remote_md5': remote_md5.hex(),
                'archived_md5': db_md5.hex(),
            })
            logger.warning(
                f"CONFLICT: {basename} has different content on device vs archive — skipped"
            )

    logger.info(
        f"Delta pre-filter: {len(pull_list):,} to pull, "
        f"{skip_count:,} already archived, "
        f"{len(conflicts):,} conflict(s)."
    )

    pulled = 0
    for remote_path, remote_size in pull_list:
        local = _staging_path(remote_path, wa_media_root, staging_dir)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'partial')
        try:
            _run_adb(['adb', 'pull', remote_path, local], logger)
        except KeyboardInterrupt:
            _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'partial')
            raise
        except Exception as e:
            stderr = ''
            if hasattr(e, 'stderr') and e.stderr:
                stderr = e.stderr.decode(errors='replace')
            reason = _classify_adb_error(stderr)
            if 'device not found' in stderr or 'device offline' in stderr or \
                    'error: closed' in stderr:
                _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'partial')
                raise RuntimeError(
                    f"Device disconnected during pull of {remote_path}: {reason}"
                ) from e
            logger.error(f"Failed to pull {remote_path}: {reason}")
            _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'partial')
            continue
        if not os.path.exists(local):
            logger.error(
                f"ADB pull reported success but file not found locally: {local}"
            )
            _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'partial')
            continue
        if os.path.getsize(local) != remote_size:
            logger.warning(
                f"Pulled file is truncated (expected {remote_size} B, "
                f"got {os.path.getsize(local)} B): {remote_path}"
            )
            _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'partial')
            continue
        _arc.upsert_adb_pull_state(conn, remote_path, device_serial, 'done')
        pulled += 1
        logger.debug(f"Pulled: {remote_path}")

    logger.info(f"Pull complete: {pulled:,} file(s) pulled.")
    return pulled, skip_count, conflicts


def write_adb_conflicts_report(report_path: str, conflicts: list, logger):
    """Write ADB pull conflicts to a CSV file — requires user intervention."""
    if not conflicts:
        return
    fieldnames = ['remote_path', 'remote_md5', 'archived_md5']
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(conflicts)
    logger.warning(
        f"ADB conflicts report written to: {report_path} "
        f"({len(conflicts)} file(s) with same name/size but different content — "
        "review and resolve manually)"
    )


# ---------------------------------------------------------------------------
# Purge Device (Free storage on phone safely)
# ---------------------------------------------------------------------------

def purge_device_media(output_root: str,
                       conn: sqlite3.Connection,
                       business: bool = False,
                       dry_run: bool = True,
                       logger: logging.Logger | None = None) -> tuple[dict, list[dict]]:
    """
    Safely delete backed-up & verified media from the mobile phone via ADB.
    Strictly protects databases, keys, and any unverified files.
    """
    if logger is None:
        logger = logging.getLogger('wab_purge')

    from . import verifier

    # Gatekeeper 1: PC Archive Integrity Check
    logger.info("Executing mandatory PC archive integrity check before device purge...")
    stats_v, _ = verifier.verify_archive(output_root, None, conn, logger)
    if not stats_v.get('is_verified', False):
        logger.error(
            "SAFETY VIOLATION: PC Archive is incomplete or corrupted!\n"
            "  Zero files will be deleted from the phone to prevent data loss.\n"
            "  Run 'wab-archiver verify' to inspect issues."
        )
        raise RuntimeError("Integrity verification failed; cannot purge device.")

    if not check_adb(logger) or not check_device_connected(logger):
        raise RuntimeError("Device not available for purge.")

    paths = detect_device_whatsapp_paths(business, logger)
    wa_media_root = paths['media_root']
    md5_binary = probe_md5_binary(logger)

    # Load archive mappings
    db_files = dict(conn.execute("SELECT original_path, md5 FROM files").fetchall())
    archive_copies_map: dict[str, list[str]] = {}
    for orig, arc in conn.execute("SELECT original_path, archive_path FROM archive_copies").fetchall():
        archive_copies_map.setdefault(orig, []).append(arc)

    remote_files = enumerate_remote_files(wa_media_root, logger)
    stats = {
        'scanned': len(remote_files),
        'protected_skipped': 0,
        'unarchived_skipped': 0,
        'mismatched_skipped': 0,
        'missing_pc_copy_skipped': 0,
        'eligible': 0,
        'deleted': 0,
        'bytes_freed': 0,
        'errors': 0,
    }
    audit_rows = []
    timestamp_now = datetime.datetime.now().isoformat()

    logger.info(f"Evaluating {len(remote_files)} remote files for safe deletion on phone...")

    for remote_path, remote_size in remote_files:
        # 1. Protection check
        if is_protected_remote_file(remote_path):
            stats['protected_skipped'] += 1
            logger.debug(f"PROTECTED (kept on phone): {remote_path}")
            continue

        # 2. Key matching
        rel = remote_path[len(wa_media_root):].lstrip('/')
        orig_key = None
        if rel in db_files:
            orig_key = rel
        elif f"Media/{rel}" in db_files:
            orig_key = f"Media/{rel}"

        if orig_key is None:
            stats['unarchived_skipped'] += 1
            logger.debug(f"UNARCHIVED (kept on phone): {rel}")
            continue

        # 3. Check PC archive copy on disk
        arc_paths = archive_copies_map.get(orig_key, [])
        pc_copy_verified = False
        expected_md5 = db_files[orig_key]
        for arc_rel in arc_paths:
            pc_full = os.path.join(output_root, *arc_rel.split('/'))
            if os.path.isfile(pc_full):
                try:
                    if file_md5(pc_full) == expected_md5:
                        pc_copy_verified = True
                        break
                except Exception:
                    pass

        if not pc_copy_verified:
            stats['missing_pc_copy_skipped'] += 1
            logger.warning(f"PC COPY MISSING/CORRUPT (kept on phone): {rel}")
            continue

        # 4. Check remote MD5 on phone
        try:
            rem_md5 = _remote_md5(remote_path, md5_binary, logger)
        except Exception as e:
            stats['errors'] += 1
            logger.warning(f"Could not read hash for {remote_path} on phone: {e}")
            continue

        if rem_md5 != expected_md5:
            stats['mismatched_skipped'] += 1
            logger.warning(f"HASH MISMATCH on phone (kept on phone): {rel}")
            continue

        # File is 100% verified on PC!
        stats['eligible'] += 1
        stats['bytes_freed'] += remote_size

        if dry_run:
            logger.info(f"[DRY RUN] Would delete from phone: {rel} ({remote_size:,} bytes)")
            audit_rows.append({
                'remote_path': remote_path,
                'status': 'DRY_RUN_ELIGIBLE',
                'size': remote_size,
                'md5': rem_md5.hex(),
                'timestamp': timestamp_now,
            })
        else:
            try:
                _run_adb(['adb', 'shell', f'rm "{remote_path}"'], logger)
                stats['deleted'] += 1
                logger.info(f"DELETED FROM PHONE: {rel} ({remote_size:,} bytes)")
                audit_rows.append({
                    'remote_path': remote_path,
                    'status': 'DELETED',
                    'size': remote_size,
                    'md5': rem_md5.hex(),
                    'timestamp': timestamp_now,
                })
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Failed to delete {remote_path} on phone: {e}")
                audit_rows.append({
                    'remote_path': remote_path,
                    'status': f"ERROR: {e}",
                    'size': remote_size,
                    'md5': rem_md5.hex(),
                    'timestamp': timestamp_now,
                })

    return stats, audit_rows


# ---------------------------------------------------------------------------
# Restore (Reconstruct WhatsApp on device)
# ---------------------------------------------------------------------------

def push_media_to_device(output_root: str,
                         conn: sqlite3.Connection,
                         business: bool = False,
                         dry_run: bool = False,
                         logger: logging.Logger | None = None) -> tuple[dict, list[dict]]:
    """
    Restore WhatsApp media files from the PC archive directly back to the phone.
    Reconstructs exact relative subfolder structure in the device's WhatsApp/Media/.
    """
    if logger is None:
        logger = logging.getLogger('wab_restore_device')

    if not check_adb(logger) or not check_device_connected(logger):
        raise RuntimeError("Device not available for restore.")

    paths = detect_device_whatsapp_paths(business, logger)
    wa_media_root = paths['media_root']

    # Load mappings
    restore_map: dict[str, list[str]] = {}
    for original_path, archive_path in conn.execute(
        "SELECT original_path, archive_path FROM archive_copies ORDER BY original_path, rowid"
    ):
        restore_map.setdefault(original_path, []).append(archive_path)

    stats = {'restored': 0, 'skipped': 0, 'unrestorable': 0, 'warnings': 0}
    report_rows = []
    restored_remote_paths = []

    logger.info(f"Restoring {len(restore_map)} unique files to device at {wa_media_root}...")

    for original_path, archive_paths in restore_map.items():
        src = None
        src_rel = None
        for rel_path in archive_paths:
            candidate = os.path.join(output_root, *rel_path.split('/'))
            if os.path.isfile(candidate):
                src = candidate
                src_rel = rel_path
                break

        if src is None:
            stats['unrestorable'] += 1
            report_rows.append({
                'original_path': original_path,
                'status': 'unrestorable',
                'details': 'No local copy found in PC archive',
            })
            continue

        # Determine target path on device
        sub_rel = original_path
        if sub_rel.startswith('Media/'):
            sub_rel = sub_rel[len('Media/'):]
        remote_dest = f"{wa_media_root}/{sub_rel}".replace('\\', '/')

        if dry_run:
            logger.info(f"[DRY RUN] Would restore to device: {src} -> {remote_dest}")
            stats['restored'] += 1
            continue

        remote_dir = posixpath.dirname(remote_dest)
        try:
            _run_adb(['adb', 'shell', f'mkdir -p "{remote_dir}"'], logger)
            _run_adb(['adb', 'push', src, remote_dest], logger)
            stats['restored'] += 1
            restored_remote_paths.append(remote_dest)
            logger.debug(f"Restored to phone: {remote_dest}")
        except Exception as e:
            stats['warnings'] += 1
            logger.error(f"Error restoring {original_path} to phone: {e}")
            report_rows.append({
                'original_path': original_path,
                'status': f"error: {e}",
                'details': str(e),
            })

    if not dry_run and restored_remote_paths:
        trigger_media_scan(restored_remote_paths, logger)

    return stats, report_rows


def push_database_to_device(output_root: str,
                            business: bool = False,
                            dry_run: bool = False,
                            logger: logging.Logger | None = None) -> bool:
    """
    Restore encrypted WhatsApp database (msgstore.db.cryptXX) to phone Databases/ folder.
    """
    if logger is None:
        logger = logging.getLogger('wab_restore_db')

    if not check_adb(logger) or not check_device_connected(logger):
        raise RuntimeError("Device not available for database restore.")

    paths = detect_device_whatsapp_paths(business, logger)
    db_remote_dir = paths['databases_root']

    # Locate database in PC archive
    db_candidates = [
        os.path.join(output_root, WA_DATABASES_DIR_NAME),
        output_root,
    ]
    target_local_db = None
    for cand_dir in db_candidates:
        if not os.path.isdir(cand_dir):
            continue
        for fname in os.listdir(cand_dir):
            lower = fname.lower()
            if any(lower.endswith(ext) for ext in ('.crypt15', '.crypt14', '.crypt12', '.db')):
                if fname != '.wa_media_archiver.db':
                    target_local_db = os.path.join(cand_dir, fname)
                    break
        if target_local_db:
            break

    if not target_local_db:
        logger.warning("No database file found in PC archive to push to phone.")
        return False

    db_name = os.path.basename(target_local_db)
    remote_dest = f"{db_remote_dir}/{db_name}".replace('\\', '/')

    if dry_run:
        logger.info(f"[DRY RUN] Would restore database to phone: {target_local_db} -> {remote_dest}")
        return True

    try:
        _run_adb(['adb', 'shell', f'mkdir -p "{db_remote_dir}"'], logger)
        _run_adb(['adb', 'push', target_local_db, remote_dest], logger)
        logger.info(f"Database successfully restored to phone: {remote_dest}")
        return True
    except Exception as e:
        logger.error(f"Failed to restore database to phone: {e}")
        return False


def trigger_media_scan(remote_paths: list[str], logger: logging.Logger | None = None):
    """Notify Android MediaScanner of restored media files so gallery & WhatsApp detect them."""
    if not remote_paths:
        return
    if logger:
        logger.info(f"Notifying Android MediaScanner of restored media files...")
    dirs = sorted(set(posixpath.dirname(p) for p in remote_paths))
    for d in dirs:
        try:
            _run_adb(['adb', 'shell', f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://{d}"'], logger)
        except Exception as e:
            if logger:
                logger.debug(f"MediaScanner broadcast notice for {d}: {e}")
