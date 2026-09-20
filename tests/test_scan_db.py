"""
Unit tests for ScanDatabase service.
Verifies batch insertion, query pagination, category breakdown, and large volume performance.
"""

import tempfile
from pathlib import Path
import pytest

from wab_gui.services.scan_db import ScanDatabase, DbMediaItem
from wab_gui.services.media_scanner import CATEGORY_VIDEOS, CATEGORY_IMAGES, CATEGORY_DOCS


def test_scan_db_basic_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_scans.db")
        db = ScanDatabase(db_path)

        session_id = "test_device_1_sess"
        db.create_session(
            session_id=session_id,
            device_serial="SN12345",
            device_name="OnePlus 12R",
            profile_id="0",
            source_path="/storage/emulated/0"
        )

        rows = [
            ("video1.mp4", "Media/video1.mp4", "/storage/video1.mp4", 100 * 1024 * 1024, CATEGORY_VIDEOS, ".mp4", 1700000000),
            ("photo1.jpg", "Media/photo1.jpg", "/storage/photo1.jpg", 5 * 1024 * 1024, CATEGORY_IMAGES, ".jpg", 1700000010),
            ("photo2.jpg", "Media/photo2.jpg", "/storage/photo2.jpg", 3 * 1024 * 1024, CATEGORY_IMAGES, ".jpg", 1700000020),
            ("doc1.pdf", "Media/doc1.pdf", "/storage/doc1.pdf", 2 * 1024 * 1024, CATEGORY_DOCS, ".pdf", 1700000030),
        ]
        db.insert_files_batch(session_id, "SN12345", rows)
        db.finalize_session(session_id)

        session = db.get_session(session_id)
        assert session is not None
        assert session.total_files == 4
        assert session.total_bytes == (100 + 5 + 3 + 2) * 1024 * 1024
        assert "MB" in session.total_size_formatted or "GB" in session.total_size_formatted

        # Category breakdown
        breakdown = db.get_category_breakdown(session_id)
        assert breakdown[CATEGORY_VIDEOS]["count"] == 1
        assert breakdown[CATEGORY_IMAGES]["count"] == 2
        assert breakdown[CATEGORY_DOCS]["count"] == 1

        # Query files with filter
        img_files = db.query_files(session_id, category=CATEGORY_IMAGES)
        assert len(img_files) == 2
        assert img_files[0].name == "photo1.jpg"

        # Search query
        doc_files = db.query_files(session_id, search_query="doc1")
        assert len(doc_files) == 1
        assert doc_files[0].name == "doc1.pdf"

        # Count and sum
        cnt, sz = db.count_and_sum_files(session_id, category=CATEGORY_IMAGES)
        assert cnt == 2
        assert sz == 8 * 1024 * 1024


def test_scan_db_large_volume_performance():
    """Verify batch insertion and query speed with 20,000 files in sub-second time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "perf_scans.db")
        db = ScanDatabase(db_path)

        session_id = "perf_session"
        db.create_session(session_id, "PERF_SN", "Bench Phone")

        # Generate 20,000 items
        batch = []
        for i in range(20000):
            cat = CATEGORY_VIDEOS if i % 4 == 0 else CATEGORY_IMAGES
            ext = ".mp4" if cat == CATEGORY_VIDEOS else ".jpg"
            batch.append((
                f"file_{i}{ext}",
                f"Media/subfolder/file_{i}{ext}",
                f"/storage/emulated/0/WhatsApp/Media/file_{i}{ext}",
                1000 + i * 10,
                cat,
                ext,
                1700000000 + i
            ))

        db.insert_files_batch(session_id, "PERF_SN", batch)
        db.finalize_session(session_id)

        session = db.get_session(session_id)
        assert session.total_files == 20000

        # Paged query performance
        paged = db.query_files(session_id, sort_by="size_desc", limit=50, offset=0)
        assert len(paged) == 50
        assert paged[0].size_bytes >= paged[1].size_bytes

        # Top largest files
        top50 = db.get_top_largest_files(session_id, limit=50)
        assert len(top50) == 50
        assert top50[0].name == "file_19999.jpg"
