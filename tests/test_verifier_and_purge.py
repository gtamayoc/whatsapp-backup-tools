import argparse
import hashlib
import os
import sqlite3
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from shared.hashing import file_md5
from wab_archiver import archive_db as arc
from wab_archiver import adb_extractor
from wab_archiver import main as wa
from wab_archiver import verifier


def _seed_archive(tmp_path, original_path, archive_rel, content=b'test media content'):
    """Insert DB row and write the archive copy file."""
    conn = arc.open_archive_db(str(tmp_path))
    md5 = hashlib.md5(content).digest()
    cur = conn.cursor()
    arc.record_file_archived(cur, original_path, md5, archive_rel, len(content))
    conn.commit()
    conn.close()

    archive_file = tmp_path.joinpath(*archive_rel.split('/'))
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    archive_file.write_bytes(content)
    return archive_file


# ===========================================================================
# Verifier Tests
# ===========================================================================

class TestVerifier:
    def test_verify_intact_archive(self, tmp_path):
        _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                      'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')
        _seed_archive(tmp_path, 'Media/WhatsApp Audio/audio1.opus',
                      'Groups/Friends/2024/audio1.opus', b'AudioClip')

        logger = MagicMock()
        conn = arc.open_archive_db(str(tmp_path))
        stats, report = verifier.verify_archive(str(tmp_path), None, conn, logger)
        conn.close()

        assert stats['total_archive_entries'] == 2
        assert stats['archive_ok'] == 2
        assert stats['archive_corrupted'] == 0
        assert stats['archive_missing'] == 0
        assert stats['is_verified'] is True
        assert len(report) == 0

    def test_verify_corrupted_archive_detects_hash_mismatch(self, tmp_path):
        arc_file = _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                                 'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')
        # Corrupt the file on disk
        arc_file.write_bytes(b'TamperedPhoto')

        logger = MagicMock()
        conn = arc.open_archive_db(str(tmp_path))
        stats, report = verifier.verify_archive(str(tmp_path), None, conn, logger)
        conn.close()

        assert stats['archive_corrupted'] == 1
        assert stats['archive_ok'] == 0
        assert stats['is_verified'] is False
        assert len(report) == 1
        assert report[0]['status'] == 'CORRUPTED_ARCHIVE'

    def test_verify_missing_archive_file(self, tmp_path):
        arc_file = _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                                 'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')
        arc_file.unlink()

        logger = MagicMock()
        conn = arc.open_archive_db(str(tmp_path))
        stats, report = verifier.verify_archive(str(tmp_path), None, conn, logger)
        conn.close()

        assert stats['archive_missing'] == 1
        assert stats['is_verified'] is False
        assert len(report) == 1
        assert report[0]['status'] == 'MISSING_ARCHIVE'

    def test_verify_database_integrity(self, tmp_path):
        # Place a valid SQLite DB in Whatsapp Databases/
        wa_db_dir = tmp_path / "Whatsapp Databases"
        wa_db_dir.mkdir(parents=True)
        sample_db = wa_db_dir / "msgstore.db"
        with sqlite3.connect(str(sample_db)) as c:
            c.execute("CREATE TABLE test (id INT);")
            c.commit()

        _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                      'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')

        logger = MagicMock()
        conn = arc.open_archive_db(str(tmp_path))
        stats, report = verifier.verify_archive(str(tmp_path), None, conn, logger)
        conn.close()

        assert stats['db_ok'] >= 1
        assert stats['db_corrupted'] == 0
        assert stats['is_verified'] is True

        # Now corrupt the database file with garbage bytes
        sample_db.write_bytes(b'CorruptedHeaderNotASQLiteDB' * 10)
        conn2 = arc.open_archive_db(str(tmp_path))
        stats2, report2 = verifier.verify_archive(str(tmp_path), None, conn2, logger)
        conn2.close()

        assert stats2['db_corrupted'] >= 1
        assert stats2['is_verified'] is False

    def test_is_archive_verified_helper(self, tmp_path):
        _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                      'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')
        logger = MagicMock()
        assert verifier.is_archive_verified(str(tmp_path), logger=logger) is True

    def test_run_verify_mode_failure_exits(self, tmp_path):
        arc_file = _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                                 'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')
        arc_file.write_bytes(b'BadData')

        args = argparse.Namespace(output=str(tmp_path), source=None)
        logger = MagicMock()
        with pytest.raises(SystemExit):
            verifier.run_verify_mode(args, logger)

        report_file = tmp_path / "verification_report.csv"
        assert report_file.exists()


# ===========================================================================
# Purge Device (Free Space on Phone) Tests
# ===========================================================================

class TestPurgeDevice:
    def test_is_protected_remote_file(self):
        # Must protect DBs, crypt files, keys, and backups
        assert adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Databases/msgstore.db.crypt15")
        assert adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Databases/msgstore.db")
        assert adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Databases/msgstore.db-wal")
        assert adb_extractor.is_protected_remote_file("wa.db")
        assert adb_extractor.is_protected_remote_file("key")
        assert adb_extractor.is_protected_remote_file("whatsapp_backup.key")
        assert adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Backups/wallpaper.backup")

        # Media files should NOT be protected
        assert not adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Media/WhatsApp Images/photo.jpg")
        assert not adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Media/WhatsApp Video/clip.mp4")
        assert not adb_extractor.is_protected_remote_file("/sdcard/WhatsApp/Media/WhatsApp Audio/audio.opus")

    @patch('wab_archiver.adb_extractor.check_device_connected', return_value=True)
    @patch('wab_archiver.adb_extractor.check_adb', return_value=True)
    def test_purge_aborts_if_archive_verification_fails(self, _adb, _dev, tmp_path):
        # Create archive with corrupted file
        arc_file = _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                                 'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')
        arc_file.write_bytes(b'CorruptedFile')

        conn = arc.open_archive_db(str(tmp_path))
        logger = MagicMock()

        # purge_device_media MUST refuse to run and raise RuntimeError
        with pytest.raises(RuntimeError, match="cannot purge device"):
            adb_extractor.purge_device_media(
                output_root=str(tmp_path),
                conn=conn,
                business=False,
                dry_run=False,
                logger=logger,
            )
        conn.close()

    @patch('wab_archiver.adb_extractor.check_device_connected', return_value=True)
    @patch('wab_archiver.adb_extractor.check_adb', return_value=True)
    @patch('wab_archiver.adb_extractor.probe_md5_binary', return_value='md5sum')
    @patch('wab_archiver.adb_extractor.detect_device_whatsapp_paths')
    @patch('wab_archiver.adb_extractor.enumerate_remote_files')
    @patch('wab_archiver.adb_extractor._remote_md5')
    @patch('wab_archiver.adb_extractor._run_adb')
    def test_purge_device_media_dry_run(self, mock_run, mock_md5, mock_enum, mock_paths,
                                        _probe, _adb, _dev, tmp_path):
        content = b'AlicePhoto123'
        _seed_archive(tmp_path, 'Media/WhatsApp Images/img1.jpg',
                      'Contacts/Alice/2024/Received/img1.jpg', content)

        media_root = '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media'
        mock_paths.return_value = {
            'whatsapp_root': '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp',
            'media_root': media_root,
            'databases_root': '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases',
            'is_scoped': True,
            'exists': True,
        }
        remote_file = f"{media_root}/WhatsApp Images/img1.jpg"
        mock_enum.return_value = [(remote_file, len(content))]
        mock_md5.return_value = hashlib.md5(content).digest()

        conn = arc.open_archive_db(str(tmp_path))
        logger = MagicMock()
        stats, audit = adb_extractor.purge_device_media(
            output_root=str(tmp_path),
            conn=conn,
            business=False,
            dry_run=True,
            logger=logger,
        )
        conn.close()

        assert stats['eligible'] == 1
        assert stats['bytes_freed'] == len(content)
        assert stats['deleted'] == 0  # Dry run: rm was NOT called
        mock_run.assert_not_called()
        assert len(audit) == 1
        assert audit[0]['status'] == 'DRY_RUN_ELIGIBLE'

    @patch('wab_archiver.adb_extractor.check_device_connected', return_value=True)
    @patch('wab_archiver.adb_extractor.check_adb', return_value=True)
    @patch('wab_archiver.adb_extractor.probe_md5_binary', return_value='md5sum')
    @patch('wab_archiver.adb_extractor.detect_device_whatsapp_paths')
    @patch('wab_archiver.adb_extractor.enumerate_remote_files')
    @patch('wab_archiver.adb_extractor._remote_md5')
    @patch('wab_archiver.adb_extractor._run_adb')
    def test_purge_device_media_deletes_only_verified_media(self, mock_run, mock_md5, mock_enum, mock_paths,
                                                           _probe, _adb, _dev, tmp_path):
        content_v = b'VerifiedPhoto'
        _seed_archive(tmp_path, 'Media/WhatsApp Images/verified.jpg',
                      'Contacts/Alice/2024/Received/verified.jpg', content_v)

        media_root = '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media'
        mock_paths.return_value = {
            'whatsapp_root': '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp',
            'media_root': media_root,
            'databases_root': '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases',
            'is_scoped': True,
            'exists': True,
        }

        remote_verified = f"{media_root}/WhatsApp Images/verified.jpg"
        remote_mismatched = f"{media_root}/WhatsApp Images/mismatched.jpg"
        remote_unarchived = f"{media_root}/WhatsApp Images/unarchived.jpg"
        remote_protected_db = f"{media_root}/msgstore.db.crypt15"

        mock_enum.return_value = [
            (remote_verified, len(content_v)),
            (remote_mismatched, 100),
            (remote_unarchived, 200),
            (remote_protected_db, 500),
        ]

        def md5_side_effect(remote_path, *args, **kwargs):
            if remote_path == remote_verified:
                return hashlib.md5(content_v).digest()
            return b'wronghash1234567'

        mock_md5.side_effect = md5_side_effect

        conn = arc.open_archive_db(str(tmp_path))
        logger = MagicMock()
        stats, audit = adb_extractor.purge_device_media(
            output_root=str(tmp_path),
            conn=conn,
            business=False,
            dry_run=False,
            logger=logger,
        )
        conn.close()

        assert stats['deleted'] == 1
        assert stats['protected_skipped'] >= 1
        assert stats['unarchived_skipped'] >= 1
        assert stats['bytes_freed'] == len(content_v)

        # Ensure rm was called ONLY for the verified media file
        assert mock_run.call_count == 1
        call_args = mock_run.call_args[0][0]
        assert 'rm' in call_args[2]
        assert remote_verified in call_args[2]


# ===========================================================================
# Restore Tests
# ===========================================================================

class TestRestoreMode:
    def test_restore_local_custom_dir(self, tmp_path):
        _seed_archive(tmp_path, 'Media/WhatsApp Images/photo.jpg',
                      'Contacts/Alice/2024/Received/photo.jpg', b'RestoredAlice')

        target_dir = tmp_path / "custom_restore"
        args = argparse.Namespace(
            output=str(tmp_path),
            to_device=False,
            to_dir=str(target_dir),
            include_db=False,
            dry_run=False,
        )
        logger = MagicMock()
        wa.run_restore_mode(args, logger)

        restored_file = target_dir / "Media" / "WhatsApp Images" / "photo.jpg"
        assert restored_file.exists()
        assert restored_file.read_bytes() == b'RestoredAlice'

    @patch('wab_archiver.adb_extractor.check_device_connected', return_value=True)
    @patch('wab_archiver.adb_extractor.check_adb', return_value=True)
    @patch('wab_archiver.adb_extractor.detect_device_whatsapp_paths')
    @patch('wab_archiver.adb_extractor._run_adb')
    @patch('wab_archiver.adb_extractor.trigger_media_scan')
    def test_restore_to_device(self, mock_scan, mock_run, mock_paths, _adb, _dev, tmp_path):
        _seed_archive(tmp_path, 'Media/WhatsApp Images/photo.jpg',
                      'Contacts/Alice/2024/Received/photo.jpg', b'PhotoForDevice')

        media_root = '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media'
        mock_paths.return_value = {
            'whatsapp_root': '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp',
            'media_root': media_root,
            'databases_root': '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases',
            'is_scoped': True,
            'exists': True,
        }

        conn = arc.open_archive_db(str(tmp_path))
        logger = MagicMock()
        stats, report = adb_extractor.push_media_to_device(
            output_root=str(tmp_path),
            conn=conn,
            business=False,
            dry_run=False,
            logger=logger,
        )
        conn.close()

        assert stats['restored'] == 1
        assert mock_run.called
        mock_scan.assert_called_once()


class TestCLIIntegration:
    def test_warn_network_paths_handles_subcommand_namespaces(self):
        logger = MagicMock()
        # verify args namespace (no wa_roots)
        args_verify = argparse.Namespace(command='verify', output='D:/backup whatsapp/001', log=None)
        wa._warn_network_paths(args_verify, logger)

        # restore args namespace (no wa_roots)
        args_restore = argparse.Namespace(command='restore', output='D:/backup whatsapp/001', log=None)
        wa._warn_network_paths(args_restore, logger)

        # purge args namespace (no wa_roots)
        args_purge = argparse.Namespace(command='purge-device', output='D:/backup whatsapp/001', log=None)
        wa._warn_network_paths(args_purge, logger)

    def test_main_verify_command_with_spaces_in_path(self, tmp_path, monkeypatch):
        out_dir = tmp_path / "backup whatsapp" / "001"
        out_dir.mkdir(parents=True)
        _seed_archive(out_dir, 'Media/WhatsApp Images/img1.jpg',
                      'Contacts/Alice/2024/Received/img1.jpg', b'AlicePhoto')

        monkeypatch.setattr('sys.argv', ['wab-archiver', 'verify', '-o', str(out_dir)])
        # Should execute successfully without throwing AttributeError
        wa.main()

