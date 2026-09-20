"""
High-performance virtualized QAbstractTableModel for WhatsApp media items.
Renders tens of thousands of items with smooth 60 FPS scrolling and minimal RAM usage.
"""

from __future__ import annotations
from typing import List, Optional
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from wab_gui.services.scan_db import DbMediaItem, ScanDatabase
from wab_gui.services.media_scanner import (
    CATEGORY_VIDEOS, CATEGORY_IMAGES, CATEGORY_AUDIOS,
    CATEGORY_DOCS, CATEGORY_DATABASES, CATEGORY_BACKUPS
)
from wab_gui.theme import (
    COLOR_BLACK_50, COLOR_BLACK_100, COLOR_BLACK_200, COLOR_BLACK_300,
    COLOR_BLACK_400, COLOR_BLACK_500
)


class MediaTableModel(QAbstractTableModel):
    """Virtualized table model to render large file collections without UI freezes."""

    COLUMNS = [
        "Nombre de Archivo",
        "Categoría",
        "Tamaño",
        "Ruta Relativa en WhatsApp"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[DbMediaItem] = []
        self._total_matched_count: int = 0
        self._total_matched_bytes: int = 0

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None

        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return item.name
            elif col == 1:
                return item.category
            elif col == 2:
                return item.size_formatted
            elif col == 3:
                return item.relative_path

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 2:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                # Color code category tag
                if item.category == CATEGORY_VIDEOS:
                    return QColor(COLOR_BLACK_100)
                elif item.category == CATEGORY_IMAGES:
                    return QColor(COLOR_BLACK_200)
                elif item.category == CATEGORY_DOCS:
                    return QColor(COLOR_BLACK_300)
                elif item.category == CATEGORY_AUDIOS:
                    return QColor(COLOR_BLACK_400)
                else:
                    return QColor(COLOR_BLACK_500)
            elif col == 3:
                return QColor(COLOR_BLACK_500)

        elif role == Qt.ItemDataRole.UserRole:
            # Full item access
            return item

        return None

    def set_items(self, items: List[DbMediaItem], total_count: Optional[int] = None, total_bytes: Optional[int] = None):
        """Update model data with Qt beginResetModel."""
        self.beginResetModel()
        self._items = items
        self._total_matched_count = total_count if total_count is not None else len(items)
        if total_bytes is not None:
            self._total_matched_bytes = total_bytes
        else:
            self._total_matched_bytes = sum(it.size_bytes for it in items)
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._items = []
        self._total_matched_count = 0
        self._total_matched_bytes = 0
        self.endResetModel()

    def get_item(self, row: int) -> Optional[DbMediaItem]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def get_all_items(self) -> List[DbMediaItem]:
        return self._items

    @property
    def total_matched_count(self) -> int:
        return self._total_matched_count

    @property
    def total_matched_bytes(self) -> int:
        return self._total_matched_bytes
