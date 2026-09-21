"""
Integrity verification module for WhatsApp archives.

Verifies that all files recorded in .wa_media_archiver.db exist on disk,
match their expected MD5 hashes, verifies database health and encrypted backup headers,
and optionally compares parity with the original source directory.
"""

import csv
import datetime
import logging
import os
import sqlite3

from shared.hashing import file_md5
from shared.source_detection import WA_DATABASES_DIR_NAME
from . import archive_db


def check_sqlite_integrity(db_path: str, logger: logging.Logger) -> bool:
    """Verify SQLite database integrity using PRAGMA integrity_check."""
    if not os.path.isfile(db_path):
        return False
    try:
        uri = f"file:{os.path.abspath(db_path)}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            res = conn.execute("PRAGMA integrity_check").fetchall()
            if res != [('ok',)]:
                logger.error(f"SQLite integrity check failed on {db_path}: {res}")
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking SQLite integrity on {db_path}: {e}")
        return False


def verify_archive(output_root: str,
                   source_root: str | None,
                   conn: sqlite3.Connection,
                   logger: logging.Logger) -> tuple[dict, list[dict]]:
    """
    Perform a complete cryptographic integrity verification.

    Returns (stats, report_rows).
    """
    archive_db.check_db_health(conn, logger)
    archive_db.sync_raw_folder_to_archive_db(output_root, conn, logger)

    stats = {
        'total_archive_entries': 0,
        'archive_ok': 0,
        'archive_corrupted': 0,
        'archive_missing': 0,
        'db_checked': 0,
        'db_ok': 0,
        'db_corrupted': 0,
        'source_checked': 0,
        'source_ok': 0,
        'source_mismatched': 0,
        'source_missing': 0,
        'unarchived_source_files': 0,
        'is_verified': False,
    }
    report_rows = []

    # 1. Verify Archive Database (.wa_media_archiver.db) thorough integrity
    stats['db_checked'] += 1
    archive_db_path = os.path.join(output_root, '.wa_media_archiver.db')
    if not check_sqlite_integrity(archive_db_path, logger):
        stats['db_corrupted'] += 1
        report_rows.append({
            'original_path': '.wa_media_archiver.db',
            'archive_path': '.wa_media_archiver.db',
            'status': 'CORRUPTED_DATABASE',
            'expected_md5': '',
            'actual_md5': '',
            'details': 'SQLite PRAGMA integrity_check failed on archive state database',
        })
    else:
        stats['db_ok'] += 1

    # Check any extracted WhatsApp databases in archive
    for candidate_dir in (os.path.join(output_root, WA_DATABASES_DIR_NAME), output_root):
        if not os.path.isdir(candidate_dir):
            continue
        for fname in os.listdir(candidate_dir):
            full_path = os.path.join(candidate_dir, fname)
            if not os.path.isfile(full_path):
                continue
            lower = fname.lower()
            if lower.endswith(('.db', '.sqlite')) and fname != '.wa_media_archiver.db':
                stats['db_checked'] += 1
                if check_sqlite_integrity(full_path, logger):
                    stats['db_ok'] += 1
                else:
                    stats['db_corrupted'] += 1
                    report_rows.append({
                        'original_path': fname,
                        'archive_path': os.path.relpath(full_path, output_root).replace(os.sep, '/'),
                        'status': 'CORRUPTED_DATABASE',
                        'expected_md5': '',
                        'actual_md5': '',
                        'details': f"SQLite integrity check failed on {fname}",
                    })
            elif any(lower.endswith(c) for c in ('.crypt12', '.crypt14', '.crypt15')):
                stats['db_checked'] += 1
                size = os.path.getsize(full_path)
                # Crypt files have minimum header + salt + iv > 67 bytes
                if size < 67:
                    stats['db_corrupted'] += 1
                    report_rows.append({
                        'original_path': fname,
                        'archive_path': os.path.relpath(full_path, output_root).replace(os.sep, '/'),
                        'status': 'CORRUPTED_CRYPT_BACKUP',
                        'expected_md5': '',
                        'actual_md5': '',
                        'details': f"Encrypted WhatsApp backup is truncated or empty ({size} bytes)",
                    })
                else:
                    stats['db_ok'] += 1

    # 2. Verify archive copies against DB
    logger.info("Verifying integrity of archived files on disk...")
    rows = conn.execute(
        "SELECT ac.original_path, ac.archive_path, f.md5, f.size "
        "FROM archive_copies ac "
        "JOIN files f ON ac.original_path = f.original_path "
        "ORDER BY ac.archive_path"
    ).fetchall()

    stats['total_archive_entries'] = len(rows)
    if not rows:
        logger.warning("No archive entries found in database.")

    known_original_paths = set()

    for original_path, archive_path, expected_md5, expected_size in rows:
        known_original_paths.add(original_path)
        archive_file = os.path.join(output_root, *archive_path.split('/'))

        if not os.path.isfile(archive_file):
            stats['archive_missing'] += 1
            logger.error(f"MISSING ARCHIVE FILE: {archive_path}")
            report_rows.append({
                'original_path': original_path,
                'archive_path': archive_path,
                'status': 'MISSING_ARCHIVE',
                'expected_md5': expected_md5.hex() if expected_md5 else '',
                'actual_md5': '',
                'details': f"File does not exist: {archive_file}",
            })
            continue

        try:
            actual_md5 = file_md5(archive_file)
        except Exception as e:
            stats['archive_corrupted'] += 1
            logger.error(f"ERROR reading archive file {archive_path}: {e}")
            report_rows.append({
                'original_path': original_path,
                'archive_path': archive_path,
                'status': 'CORRUPTED_ARCHIVE',
                'expected_md5': expected_md5.hex() if expected_md5 else '',
                'actual_md5': '',
                'details': f"Read error: {e}",
            })
            continue

        if actual_md5 != expected_md5:
            stats['archive_corrupted'] += 1
            logger.error(
                f"CORRUPTED ARCHIVE FILE (hash mismatch): {archive_path} "
                f"(expected {expected_md5.hex()}, got {actual_md5.hex()})"
            )
            report_rows.append({
                'original_path': original_path,
                'archive_path': archive_path,
                'status': 'CORRUPTED_ARCHIVE',
                'expected_md5': expected_md5.hex() if expected_md5 else '',
                'actual_md5': actual_md5.hex(),
                'details': "MD5 checksum mismatch in archive copy",
            })
        else:
            stats['archive_ok'] += 1

    logger.info(
        f"Archive disk check complete: {stats['archive_ok']} OK, "
        f"{stats['archive_corrupted']} corrupted, "
        f"{stats['archive_missing']} missing."
    )

    # 3. If source_root provided, verify source parity
    if source_root:
        if not os.path.isdir(source_root):
            logger.error(f"Source root does not exist: {source_root}")
            raise SystemExit(1)

        logger.info(f"Comparing archive with source directory: {source_root}...")

        # A) Check each recorded original file against source
        db_files = conn.execute("SELECT original_path, md5 FROM files").fetchall()
        for orig_path, exp_md5 in db_files:
            stats['source_checked'] += 1
            src_file = os.path.join(source_root, *orig_path.split('/'))

            if not os.path.isfile(src_file):
                stats['source_missing'] += 1
                logger.debug(f"Source file not present on source disk: {orig_path}")
                report_rows.append({
                    'original_path': orig_path,
                    'archive_path': '',
                    'status': 'SOURCE_FILE_MISSING',
                    'expected_md5': exp_md5.hex() if exp_md5 else '',
                    'actual_md5': '',
                    'details': "File no longer present in source directory",
                })
                continue

            try:
                src_md5 = file_md5(src_file)
            except Exception as e:
                stats['source_mismatched'] += 1
                logger.warning(f"Could not read source file {src_file}: {e}")
                report_rows.append({
                    'original_path': orig_path,
                    'archive_path': '',
                    'status': 'SOURCE_READ_ERROR',
                    'expected_md5': exp_md5.hex() if exp_md5 else '',
                    'actual_md5': '',
                    'details': f"Error reading source file: {e}",
                })
                continue

            if src_md5 != exp_md5:
                stats['source_mismatched'] += 1
                logger.warning(
                    f"SOURCE HASH MISMATCH: {orig_path} has changed since archive "
                    f"(archive: {exp_md5.hex()}, source: {src_md5.hex()})"
                )
                report_rows.append({
                    'original_path': orig_path,
                    'archive_path': '',
                    'status': 'SOURCE_HASH_MISMATCH',
                    'expected_md5': exp_md5.hex() if exp_md5 else '',
                    'actual_md5': src_md5.hex(),
                    'details': "Source file content differs from archive",
                })
            else:
                stats['source_ok'] += 1

        # B) Scan source directory for unarchived media files
        logger.info("Scanning source directory for unarchived media files...")
        for root, _, filenames in os.walk(source_root):
            for fname in filenames:
                full_src = os.path.join(root, fname)
                rel_src = os.path.relpath(full_src, source_root).replace(os.sep, '/')

                # Skip DBs, logs, temp files
                lower = fname.lower()
                if (lower.endswith(('.db', '.db-wal', '.db-shm', '.crypt12', '.crypt14', '.crypt15',
                                    '.sqlite', '.sqlite-wal', '.sqlite-shm', '.log', '.csv', '.txt'))
                        or 'databases' in rel_src.lower()
                        or 'backups' in rel_src.lower()):
                    continue

                # Check if this relative path was archived
                if rel_src not in known_original_paths:
                    # Also try checking if 'Media/' prefix matches
                    if not rel_src.startswith('Media/') and f"Media/{rel_src}" in known_original_paths:
                        continue
                    stats['unarchived_source_files'] += 1
                    try:
                        f_hash = file_md5(full_src).hex()
                    except Exception:
                        f_hash = ''
                    logger.warning(f"UNARCHIVED SOURCE FILE FOUND: {rel_src}")
                    report_rows.append({
                        'original_path': rel_src,
                        'archive_path': '',
                        'status': 'UNARCHIVED_SOURCE_FILE',
                        'expected_md5': '',
                        'actual_md5': f_hash,
                        'details': "Media file exists in source directory but was not found in archive",
                    })

    has_critical_error = (
        stats['archive_corrupted'] > 0
        or stats['archive_missing'] > 0
        or stats['db_corrupted'] > 0
        or stats['source_mismatched'] > 0
        or stats['unarchived_source_files'] > 0
    )
    stats['is_verified'] = not has_critical_error
    return stats, report_rows


def is_archive_verified(output_root: str,
                        source_root: str | None = None,
                        logger: logging.Logger | None = None) -> bool:
    """
    Safely check whether the archive is 100% intact and cryptographically verified.
    Returns True if verified, False if any error or corruption exists.
    Does NOT raise SystemExit.
    """
    if logger is None:
        logger = logging.getLogger('wab_verifier')
    try:
        conn = archive_db.open_archive_db(output_root)
    except Exception as e:
        logger.error(f"Cannot open archive database: {e}")
        return False

    try:
        stats, _ = verify_archive(output_root, source_root, conn, logger)
        return stats.get('is_verified', False)
    except Exception as e:
        logger.error(f"Verification exception: {e}")
        return False
    finally:
        conn.close()


def run_verify_mode(args, logger: logging.Logger):
    """
    Execute integrity verification.
    Raises SystemExit(1) if any corruption or critical issue is found.
    """
    logger.info(f"Opening archive database at: {args.output}")
    conn = archive_db.open_archive_db(args.output)
    try:
        source = getattr(args, 'source', None)
        stats, report_rows = verify_archive(args.output, source, conn, logger)

        report_path = os.path.join(args.output, 'verification_report.csv')
        if report_rows:
            fieldnames = ['original_path', 'archive_path', 'status',
                          'expected_md5', 'actual_md5', 'details']
            with open(report_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(report_rows)
            logger.info(f"Verification report written to: {report_path} ({len(report_rows)} issue(s))")

        logger.info("=== Verification Summary ===")
        logger.info(f"  {'Total archive entries':<25}: {stats['total_archive_entries']}")
        logger.info(f"  {'Archive files intact (OK)':<25}: {stats['archive_ok']}")
        logger.info(f"  {'Archive corrupted':<25}: {stats['archive_corrupted']}")
        logger.info(f"  {'Archive missing':<25}: {stats['archive_missing']}")
        logger.info(f"  {'Databases checked':<25}: {stats['db_checked']} ({stats['db_ok']} OK, {stats['db_corrupted']} failed)")

        if source:
            logger.info(f"  {'Source files checked':<25}: {stats['source_checked']}")
            logger.info(f"  {'Source files matching':<25}: {stats['source_ok']}")
            logger.info(f"  {'Source hash mismatches':<25}: {stats['source_mismatched']}")
            logger.info(f"  {'Source missing files':<25}: {stats['source_missing']}")
            logger.info(f"  {'Unarchived source files':<25}: {stats['unarchived_source_files']}")

        if not stats['is_verified']:
            logger.error(
                "Integrity verification FAILED! There are corrupt, missing, or unarchived files.\n"
                f"Review the report for details: {report_path}"
            )
            raise SystemExit(1)

        logger.info("SUCCESS: All archived files and databases are 100% verified and cryptographically intact.")

    finally:
        conn.close()
