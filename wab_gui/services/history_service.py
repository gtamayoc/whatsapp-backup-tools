"""
History manager for recently selected paths in wab_gui.
Stores up to 20 most recently used (MRU) paths per category in .wab_gui_profiles/path_history.json.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List, Dict

PROFILES_DIR = Path(".wab_gui_profiles")
HISTORY_FILE = PROFILES_DIR / "path_history.json"
MAX_HISTORY_ENTRIES = 20


class HistoryService:
    """Service to persist and retrieve the last 20 selected paths per category."""

    @classmethod
    def _ensure_profiles_dir(cls) -> Path:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        return PROFILES_DIR

    @classmethod
    def load_all(cls) -> Dict[str, List[str]]:
        """Load all history categories from the JSON file."""
        if not HISTORY_FILE.is_file():
            return {}
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    @classmethod
    def save_all(cls, data: Dict[str, List[str]]) -> bool:
        """Save all history categories to the JSON file."""
        try:
            cls._ensure_profiles_dir()
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    @classmethod
    def get_history(cls, category: str = "default") -> List[str]:
        """Return the list of up to 20 recent paths for a given category."""
        all_data = cls.load_all()
        paths = all_data.get(category, [])
        # Return only paths that still exist on disk
        valid_paths = [p for p in paths if os.path.exists(p)]
        return valid_paths[:MAX_HISTORY_ENTRIES]

    @classmethod
    def add_path(cls, path: str, category: str = "default") -> bool:
        """
        Add a path to the category history.
        - Moves path to the top (index 0) if already present.
        - Limits list to MAX_HISTORY_ENTRIES (20).
        - Skips non-existent or empty paths.
        """
        if not path or not path.strip():
            return False

        clean_path = os.path.abspath(path.strip()).replace(os.sep, "/")
        if not os.path.exists(clean_path):
            return False

        all_data = cls.load_all()
        category_paths = all_data.get(category, [])

        # Normalize existing entries for comparison
        normalized = [p.replace(os.sep, "/") for p in category_paths]

        # Remove if already exists (MRU behavior)
        if clean_path in normalized:
            idx = normalized.index(clean_path)
            category_paths.pop(idx)

        # Insert at the top
        category_paths.insert(0, clean_path)

        # Cap to MAX_HISTORY_ENTRIES (20)
        all_data[category] = category_paths[:MAX_HISTORY_ENTRIES]

        return cls.save_all(all_data)

    @classmethod
    def clear_history(cls, category: str = "default") -> bool:
        """Clear all stored paths for a given category."""
        all_data = cls.load_all()
        if category in all_data:
            all_data[category] = []
            return cls.save_all(all_data)
        return True
