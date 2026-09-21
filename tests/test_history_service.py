import json
import os
from pathlib import Path
from unittest.mock import patch

from wab_gui.services.history_service import HistoryService, MAX_HISTORY_ENTRIES


class TestHistoryService:
    def test_add_and_get_history(self, tmp_path, monkeypatch):
        hist_file = tmp_path / "path_history.json"
        monkeypatch.setattr("wab_gui.services.history_service.HISTORY_FILE", hist_file)
        monkeypatch.setattr("wab_gui.services.history_service.PROFILES_DIR", tmp_path)

        # Create two real test directories
        dir1 = tmp_path / "folder1"
        dir2 = tmp_path / "folder2"
        dir1.mkdir()
        dir2.mkdir()

        p1 = str(dir1).replace(os.sep, "/")
        p2 = str(dir2).replace(os.sep, "/")

        HistoryService.add_path(p1, "test_cat")
        HistoryService.add_path(p2, "test_cat")

        history = HistoryService.get_history("test_cat")
        # Most recent (p2) should be first
        assert history == [p2, p1]

    def test_mru_deduplication(self, tmp_path, monkeypatch):
        hist_file = tmp_path / "path_history.json"
        monkeypatch.setattr("wab_gui.services.history_service.HISTORY_FILE", hist_file)
        monkeypatch.setattr("wab_gui.services.history_service.PROFILES_DIR", tmp_path)

        dir1 = tmp_path / "folder1"
        dir2 = tmp_path / "folder2"
        dir1.mkdir()
        dir2.mkdir()

        p1 = str(dir1).replace(os.sep, "/")
        p2 = str(dir2).replace(os.sep, "/")

        HistoryService.add_path(p1, "test_cat")
        HistoryService.add_path(p2, "test_cat")
        # Re-add p1 -> should move to index 0 without duplicating
        HistoryService.add_path(p1, "test_cat")

        history = HistoryService.get_history("test_cat")
        assert history == [p1, p2]
        assert len(history) == 2

    def test_max_20_entries_capped(self, tmp_path, monkeypatch):
        hist_file = tmp_path / "path_history.json"
        monkeypatch.setattr("wab_gui.services.history_service.HISTORY_FILE", hist_file)
        monkeypatch.setattr("wab_gui.services.history_service.PROFILES_DIR", tmp_path)

        created_dirs = []
        for i in range(25):
            d = tmp_path / f"dir_{i:02d}"
            d.mkdir()
            p = str(d).replace(os.sep, "/")
            created_dirs.append(p)
            HistoryService.add_path(p, "capped_cat")

        history = HistoryService.get_history("capped_cat")
        assert len(history) == MAX_HISTORY_ENTRIES
        # Last added (dir_24) should be first, and oldest (dir_00..dir_04) should be pruned
        assert history[0] == created_dirs[-1]
        assert history[-1] == created_dirs[5]
        assert created_dirs[0] not in history

    def test_clear_history(self, tmp_path, monkeypatch):
        hist_file = tmp_path / "path_history.json"
        monkeypatch.setattr("wab_gui.services.history_service.HISTORY_FILE", hist_file)
        monkeypatch.setattr("wab_gui.services.history_service.PROFILES_DIR", tmp_path)

        d = tmp_path / "some_dir"
        d.mkdir()
        HistoryService.add_path(str(d), "to_clear")
        assert len(HistoryService.get_history("to_clear")) == 1

        HistoryService.clear_history("to_clear")
        assert len(HistoryService.get_history("to_clear")) == 0

    def test_nonexistent_path_not_added(self, tmp_path, monkeypatch):
        hist_file = tmp_path / "path_history.json"
        monkeypatch.setattr("wab_gui.services.history_service.HISTORY_FILE", hist_file)
        monkeypatch.setattr("wab_gui.services.history_service.PROFILES_DIR", tmp_path)

        fake_path = str(tmp_path / "does_not_exist")
        res = HistoryService.add_path(fake_path, "cat")
        assert res is False
        assert HistoryService.get_history("cat") == []


class TestPathPickerHistory:
    def test_path_picker_has_history_button_when_key_set(self, tmp_path):
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)

        from wab_gui.ui.components.path_picker import PathPicker

        picker_with_hist = PathPicker(history_key="test_key")
        assert hasattr(picker_with_hist, "btn_history")

        picker_without_hist = PathPicker()
        assert not hasattr(picker_without_hist, "btn_history")

    def test_path_picker_select_history_path_sets_text(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)

        hist_file = tmp_path / "path_history.json"
        monkeypatch.setattr("wab_gui.services.history_service.HISTORY_FILE", hist_file)
        monkeypatch.setattr("wab_gui.services.history_service.PROFILES_DIR", tmp_path)

        from wab_gui.ui.components.path_picker import PathPicker

        test_dir = tmp_path / "picked_folder"
        test_dir.mkdir()
        p = str(test_dir).replace(os.sep, "/")

        picker = PathPicker(history_key="output_dir")
        picker._select_history_path(p)

        assert picker.get_path() == p
        assert p in HistoryService.get_history("output_dir")

