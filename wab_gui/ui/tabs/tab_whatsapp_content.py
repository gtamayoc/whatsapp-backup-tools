"""
Unified WhatsApp Content Dashboard and High-Capacity Interactive Explorer.
Features:
- Instant device hotplug detection & clean "No hay dispositivo conectado" empty state.
- Strict separation between Live Connected Device and Historical Saved Scans.
- Virtualized QTableView with MediaTableModel for smooth 60 FPS scrolling with >100,000 files (>100 GB).
- Fast SQL-indexed search, category filtering, Top 50 largest files, and cumulative size metrics.
- Collapsible metrics header giving maximum vertical screen space to the file explorer.
- Preserves Apple Pro / iOS minimal design with Kigen.design Monochrome tokens.
"""

from __future__ import annotations
import os
import sys
import time
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QTableView, QHeaderView, QButtonGroup,
    QProgressBar, QMessageBox, QFileDialog, QComboBox, QStackedWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor

from wab_gui.services.media_scanner import (
    MediaScanner, ScanResult, MediaItem, format_bytes,
    CATEGORY_VIDEOS, CATEGORY_IMAGES, CATEGORY_AUDIOS, CATEGORY_DOCS,
    CATEGORY_DATABASES, CATEGORY_BACKUPS, CATEGORY_OTHER
)
from wab_gui.services.scan_db import ScanDatabase, DbMediaItem, ScanSessionRecord
from wab_gui.ui.components.media_table_model import MediaTableModel
from wab_gui.workers.extractor_worker import DirectExtractorWorker
from wab_gui.theme import (
    COLOR_BLACK_50, COLOR_BLACK_100, COLOR_BLACK_200, COLOR_BLACK_300,
    COLOR_BLACK_400, COLOR_BLACK_500, COLOR_BLACK_600, COLOR_BLACK_700,
    COLOR_BLACK_800, COLOR_BLACK_900, COLOR_BLACK_950,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_MUTED, COLOR_SURFACE
)


class ScanWorker(QThread):
    """Background worker for streaming analysis of WhatsApp content without memory exhaustion."""

    finished_sig = Signal(object)
    status_sig = Signal(str)

    def __init__(
        self,
        adb_bin: Optional[str] = None,
        serial: Optional[str] = None,
        device_name: str = "Dispositivo",
        local_path: Optional[str] = None,
        profile_id: str = "all",
        parent=None,
    ):
        super().__init__(parent)
        self.adb_bin = adb_bin
        self.serial = serial
        self.device_name = device_name
        self.local_path = local_path
        self.profile_id = profile_id

    def run(self):
        def cb(msg):
            self.status_sig.emit(msg)

        if self.adb_bin and self.serial:
            res = MediaScanner.scan_adb_device(
                self.adb_bin, self.serial, self.device_name,
                profile_id=self.profile_id, progress_cb=cb
            )
        elif self.local_path:
            res = MediaScanner.scan_local_folder(
                self.local_path, self.device_name, progress_cb=cb
            )
        else:
            res = ScanResult()

        self.finished_sig.emit(res)


class NoDevicePlaceholder(QFrame):
    """Visual waiting screen when no Android device is currently plugged in via USB."""

    refresh_requested = Signal()
    switch_to_history_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {COLOR_BLACK_950};
                border: 1px dashed {COLOR_BLACK_700};
                border-radius: 12px;
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(40, 40, 40, 40)
        lo.setSpacing(14)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon / Graphic badge
        lbl_icon = QLabel("🔌")
        lbl_icon.setStyleSheet("font-size: 48px;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(lbl_icon)

        # Title
        lbl_title = QLabel("No hay ningún dispositivo conectado")
        lbl_title.setStyleSheet(f"color: {COLOR_BLACK_50}; font-size: 20px; font-weight: 800;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(lbl_title)

        # Description
        lbl_desc = QLabel(
            "Conecte su teléfono Android mediante un cable USB para diagnosticar y explorar el almacenamiento de WhatsApp."
        )
        lbl_desc.setStyleSheet(f"color: {COLOR_BLACK_400}; font-size: 13px;")
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setWordWrap(True)
        lo.addWidget(lbl_desc)

        # Checklist container
        guide_box = QFrame()
        guide_box.setStyleSheet(f"""
            background-color: #0c0c0c;
            border: 1px solid {COLOR_BLACK_800};
            border-radius: 8px;
            padding: 14px;
        """)
        guide_lo = QVBoxLayout(guide_box)
        guide_lo.setSpacing(8)

        steps = [
            ("1", "Conecte el cable USB de su teléfono a la computadora."),
            ("2", "En su teléfono, active la opción 'Depuración por USB' (Ajustes > Opciones de desarrollador)."),
            ("3", "Acepte la ventana emergente en pantalla: '¿Permitir depuración USB de esta computadora?'.")
        ]
        for num, text in steps:
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = QLabel(num)
            badge.setStyleSheet(f"""
                background-color: {COLOR_BLACK_800};
                color: {COLOR_BLACK_50};
                font-weight: 700;
                font-size: 11px;
                border-radius: 10px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
                qproperty-alignment: AlignCenter;
            """)
            row.addWidget(badge)
            step_lbl = QLabel(text)
            step_lbl.setStyleSheet(f"color: {COLOR_BLACK_200}; font-size: 12px;")
            step_lbl.setWordWrap(True)
            row.addWidget(step_lbl, 1)
            guide_lo.addLayout(row)

        lo.addWidget(guide_box)

        # Action Buttons
        btn_lo = QHBoxLayout()
        btn_lo.setSpacing(12)
        btn_lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_refresh = QPushButton("🔄 Reintentar Detección")
        self.btn_refresh.setObjectName("primaryBtn")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        btn_lo.addWidget(self.btn_refresh)

        self.btn_history = QPushButton("🏛️ Ver Historial de Escaneos Guardados")
        self.btn_history.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a1a1a;
                border: 1px solid {COLOR_BLACK_700};
                color: {COLOR_BLACK_100};
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #262626;
                color: #ffffff;
            }}
        """)
        self.btn_history.clicked.connect(self.switch_to_history_requested.emit)
        btn_lo.addWidget(self.btn_history)

        lo.addLayout(btn_lo)


class TabWhatsAppContent(QWidget):
    """
    Unified WhatsApp Content view:
    - High-capacity virtualized file explorer with search, sorting and filtering.
    - Live Connected Device vs Historical Saved Scans separation.
    - Streaming progress and zero-freeze performance with >100 GB.
    """

    request_adb_scan = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = ScanDatabase()
        self.current_scan: Optional[ScanResult] = None
        self.active_session_id: Optional[str] = None
        self.is_historical_mode: bool = False

        self.current_category_filter: str = "Todos"
        self.current_sort: str = "size_desc"
        self.is_top_50_active: bool = False

        self.extractor_worker: Optional[DirectExtractorWorker] = None
        self.adb_bin: Optional[str] = None
        self.serial: Optional[str] = None
        self.device_name: str = "Dispositivo"
        self.output_root_dir: str = os.path.abspath("results")

        self.table_model = MediaTableModel(self)

        # Search debounce timer to prevent lag on fast typing
        self.search_debounce = QTimer(self)
        self.search_debounce.setSingleShot(True)
        self.search_debounce.setInterval(250)
        self.search_debounce.timeout.connect(self._execute_search_query)

        self._init_ui()

    def set_custom_output_root(self, root_dir: str):
        """Update single global output destination."""
        self.output_root_dir = os.path.abspath(root_dir)
        full_dest = os.path.join(self.output_root_dir, self.device_name)
        self.lbl_target_info.setText(f"Destino directo: {full_dest}")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # 1. TOP MODE SWITCHER: Live Device vs Saved Historical Scans
        mode_bar = QHBoxLayout()
        mode_bar.setSpacing(8)

        lbl_mode = QLabel("Modo:")
        lbl_mode.setStyleSheet(f"color: {COLOR_BLACK_400}; font-weight: 700; font-size: 11px;")
        mode_bar.addWidget(lbl_mode)

        self.btn_mode_live = QPushButton("📱 Dispositivo Conectado (En Vivo)")
        self.btn_mode_live.setCheckable(True)
        self.btn_mode_live.setChecked(True)
        self.btn_mode_live.setStyleSheet(self._mode_btn_style())
        self.btn_mode_live.clicked.connect(self._select_live_mode)
        mode_bar.addWidget(self.btn_mode_live)

        self.btn_mode_history = QPushButton("🏛️ Historial de Escaneos")
        self.btn_mode_history.setCheckable(True)
        self.btn_mode_history.setChecked(False)
        self.btn_mode_history.setStyleSheet(self._mode_btn_style())
        self.btn_mode_history.clicked.connect(self._select_history_mode)
        mode_bar.addWidget(self.btn_mode_history)

        # History session selector (visible only in history mode)
        self.combo_history = QComboBox()
        self.combo_history.setMinimumWidth(280)
        self.combo_history.setVisible(False)
        self.combo_history.currentIndexChanged.connect(self._on_history_session_selected)
        mode_bar.addWidget(self.combo_history)

        self.btn_delete_history = QPushButton("🗑️ Eliminar")
        self.btn_delete_history.setVisible(False)
        self.btn_delete_history.setToolTip("Eliminar el escaneo histórico seleccionado")
        self.btn_delete_history.clicked.connect(self._delete_current_history_session)
        mode_bar.addWidget(self.btn_delete_history)

        mode_bar.addStretch()

        self.lbl_device_badge = QLabel("Sin Dispositivo")
        self.lbl_device_badge.setStyleSheet(f"""
            background-color: #1a1a1a;
            color: {COLOR_BLACK_400};
            border: 1px solid {COLOR_BLACK_800};
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        mode_bar.addWidget(self.lbl_device_badge)

        main_layout.addLayout(mode_bar)

        # 2. STACKED CONTAINER: (A) No Device Placeholder, (B) Live / History Data Explorer
        self.stack = QStackedWidget()

        # Page 0: No Device Placeholder
        self.placeholder = NoDevicePlaceholder()
        self.placeholder.refresh_requested.connect(self.request_adb_scan.emit)
        self.placeholder.switch_to_history_requested.connect(self._select_history_mode)
        self.stack.addWidget(self.placeholder)

        # Page 1: Main Content Dashboard & Explorer
        self.content_widget = QWidget()
        content_lo = QVBoxLayout(self.content_widget)
        content_lo.setContentsMargins(0, 0, 0, 0)
        content_lo.setSpacing(8)

        # Top Stats Summary Row (Compact & Collapsible)
        stats_header = QFrame()
        stats_header.setObjectName("card")
        stats_lo = QVBoxLayout(stats_header)
        stats_lo.setContentsMargins(12, 8, 12, 8)
        stats_lo.setSpacing(6)

        banner_row = QHBoxLayout()
        banner_row.setSpacing(12)

        self.lbl_summary_hero = QLabel("0 B")
        self.lbl_summary_hero.setStyleSheet(f"color: {COLOR_BLACK_50}; font-size: 22px; font-weight: 800;")
        banner_row.addWidget(self.lbl_summary_hero)

        self.lbl_summary_sub = QLabel("0 archivos de WhatsApp")
        self.lbl_summary_sub.setStyleSheet(f"color: {COLOR_BLACK_400}; font-size: 12px; font-weight: 500;")
        banner_row.addWidget(self.lbl_summary_sub)

        banner_row.addStretch()

        self.btn_toggle_metrics = QPushButton("📊 Estadísticas Detalladas ▼")
        self.btn_toggle_metrics.setStyleSheet(f"""
            background-color: transparent;
            border: 1px solid {COLOR_BLACK_800};
            color: {COLOR_BLACK_300};
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
        """)
        self.btn_toggle_metrics.clicked.connect(self._toggle_metrics_panel)
        banner_row.addWidget(self.btn_toggle_metrics)

        self.btn_rescan = QPushButton("🔄 Re-Analizar")
        self.btn_rescan.clicked.connect(self.trigger_scan)
        banner_row.addWidget(self.btn_rescan)

        self.btn_hero_extract = QPushButton("🚀 Extraer Todo a Disco")
        self.btn_hero_extract.setObjectName("primaryBtn")
        self.btn_hero_extract.clicked.connect(self._start_extraction)
        banner_row.addWidget(self.btn_hero_extract)

        stats_lo.addLayout(banner_row)

        # Live Animated Progress Bar
        self.bar_distribution = QProgressBar()
        self.bar_distribution.setRange(0, 100)
        self.bar_distribution.setValue(0)
        self.bar_distribution.setFormat("Listo para explorar")
        self.bar_distribution.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0d0d0d;
                border: 1px solid {COLOR_BLACK_800};
                border-radius: 6px;
                height: 14px;
                font-size: 10px;
                color: {COLOR_BLACK_200};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_BLACK_500}, stop:1 {COLOR_BLACK_100});
                border-radius: 5px;
            }}
        """)
        stats_lo.addWidget(self.bar_distribution)

        # Collapsible Detailed Category Cards (2x3 Grid)
        self.metrics_container = QWidget()
        grid_lo = QGridLayout(self.metrics_container)
        grid_lo.setContentsMargins(0, 4, 0, 0)
        grid_lo.setHorizontalSpacing(8)
        grid_lo.setVerticalSpacing(8)

        self.card_videos = self._create_compact_card("🎬 Videos")
        self.card_docs = self._create_compact_card("📄 Documentos")
        self.card_images = self._create_compact_card("🖼️ Fotos & Stickers")
        self.card_audios = self._create_compact_card("🎙️ Audios & Voz")
        self.card_databases = self._create_compact_card("🗄️ Bases de Datos")
        self.card_backups = self._create_compact_card("📦 Backups")

        grid_lo.addWidget(self.card_videos, 0, 0)
        grid_lo.addWidget(self.card_docs, 0, 1)
        grid_lo.addWidget(self.card_images, 0, 2)
        grid_lo.addWidget(self.card_audios, 1, 0)
        grid_lo.addWidget(self.card_databases, 1, 1)
        grid_lo.addWidget(self.card_backups, 1, 2)

        self.metrics_container.setVisible(False)  # Collapsed by default to maximize table height!
        stats_lo.addWidget(self.metrics_container)

        content_lo.addWidget(stats_header)

        # 3. INTERACTIVE FILTER & SEARCH TOOLBAR
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        lbl_filter = QLabel("Filtrar:")
        lbl_filter.setStyleSheet(f"color: {COLOR_BLACK_400}; font-weight: 600; font-size: 11px;")
        toolbar.addWidget(lbl_filter)

        self.btn_group_filter = QButtonGroup(self)
        self.filter_buttons = {}

        categories = [
            "Todos", CATEGORY_VIDEOS, CATEGORY_DOCS, CATEGORY_IMAGES,
            CATEGORY_AUDIOS, CATEGORY_DATABASES, CATEGORY_BACKUPS
        ]
        for cat in categories:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            if cat == "Todos":
                btn.setChecked(True)
            btn.setStyleSheet(self._filter_pill_style())
            btn.clicked.connect(lambda checked, c=cat: self._set_category_filter(c))
            self.btn_group_filter.addButton(btn)
            self.filter_buttons[cat] = btn
            toolbar.addWidget(btn)

        # Top 50 Largest Files quick toggle
        self.btn_top50 = QPushButton("🔥 Top 50 Mayores")
        self.btn_top50.setCheckable(True)
        self.btn_top50.setStyleSheet(self._filter_pill_style())
        self.btn_top50.clicked.connect(self._toggle_top50)
        toolbar.addWidget(self.btn_top50)

        toolbar.addSpacing(6)

        # Account / Profile selector
        lbl_profile = QLabel("Cuenta:")
        lbl_profile.setStyleSheet(f"color: {COLOR_BLACK_400}; font-weight: 600; font-size: 11px;")
        toolbar.addWidget(lbl_profile)

        self.combo_profile = QComboBox()
        self.combo_profile.addItem("Todas las Cuentas", "all")
        self.combo_profile.addItem("MultiApp (999)", "999")
        self.combo_profile.addItem("Principal (0)", "0")
        self.combo_profile.currentIndexChanged.connect(lambda idx: self.trigger_scan())
        toolbar.addWidget(self.combo_profile)

        toolbar.addSpacing(6)

        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar por nombre o ruta...")
        self.search_input.textChanged.connect(lambda: self.search_debounce.start())
        toolbar.addWidget(self.search_input, 1)

        # Sort Dropdown
        lbl_sort = QLabel("Ordenar:")
        lbl_sort.setStyleSheet(f"color: {COLOR_BLACK_400}; font-weight: 600; font-size: 11px;")
        toolbar.addWidget(lbl_sort)

        self.combo_sort = QComboBox()
        self.combo_sort.addItem("Mayor Tamaño", "size_desc")
        self.combo_sort.addItem("Menor Tamaño", "size_asc")
        self.combo_sort.addItem("Nombre (A-Z)", "name_asc")
        self.combo_sort.addItem("Nombre (Z-A)", "name_desc")
        self.combo_sort.addItem("Ruta Relativa", "path_asc")
        self.combo_sort.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.combo_sort)

        content_lo.addLayout(toolbar)

        # 4. HIGH-PERFORMANCE VIRTUALIZED QTABLEVIEW (Occupies 75-80% of vertical height)
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(False)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setShowGrid(False)

        h_header = self.table_view.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_view.setColumnWidth(0, 280)

        self.table_view.setStyleSheet(f"""
            QTableView {{
                background-color: {COLOR_BLACK_950};
                border: 1px solid {COLOR_BLACK_800};
                border-radius: 8px;
                color: {COLOR_BLACK_100};
                selection-background-color: #242424;
                selection-color: {COLOR_BLACK_50};
                outline: none;
            }}
            QHeaderView::section {{
                background-color: #121212;
                color: {COLOR_BLACK_300};
                padding: 6px;
                border: 1px solid {COLOR_BLACK_800};
                font-weight: 600;
                font-size: 11px;
            }}
            QTableView::item {{
                padding: 2px 6px;
                border-bottom: 1px solid #141414;
            }}
            QTableView::item:selected {{
                background-color: #262626;
                color: {COLOR_BLACK_50};
            }}
        """)
        content_lo.addWidget(self.table_view, 1)

        # 5. STATUS SUMMARY ROW UNDER TABLE
        status_row = QHBoxLayout()
        self.lbl_table_status = QLabel("Listo.")
        self.lbl_table_status.setStyleSheet(f"color: {COLOR_BLACK_400}; font-size: 11px;")
        status_row.addWidget(self.lbl_table_status)

        status_row.addStretch()

        self.lbl_cumulative_size = QLabel("")
        self.lbl_cumulative_size.setStyleSheet(f"color: {COLOR_BLACK_200}; font-weight: 700; font-size: 11px;")
        status_row.addWidget(self.lbl_cumulative_size)

        content_lo.addLayout(status_row)

        # 6. BOTTOM EXTRACTION ACTION BAR
        action_bar = QHBoxLayout()
        action_bar.setSpacing(10)

        dest_initial = os.path.join(self.output_root_dir, self.device_name)
        self.lbl_target_info = QLabel(f"Destino directo: {dest_initial}")
        self.lbl_target_info.setStyleSheet(f"color: {COLOR_BLACK_300}; font-weight: 500; font-size: 12px;")
        action_bar.addWidget(self.lbl_target_info)

        action_bar.addStretch()

        self.btn_open_results = QPushButton("📁 Abrir Carpeta de Destino")
        self.btn_open_results.clicked.connect(self._open_results_folder)
        action_bar.addWidget(self.btn_open_results)

        self.btn_extract_selection = QPushButton("🚀 Extraer Selección / Vista a Disco")
        self.btn_extract_selection.setObjectName("primaryBtn")
        self.btn_extract_selection.clicked.connect(self._start_extraction)
        action_bar.addWidget(self.btn_extract_selection)

        content_lo.addLayout(action_bar)

        self.stack.addWidget(self.content_widget)
        main_layout.addWidget(self.stack, 1)

        # Initial state: No device connected
        self.stack.setCurrentIndex(0)

    def _mode_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: #141414;
                border: 1px solid {COLOR_BLACK_800};
                color: {COLOR_BLACK_400};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #202020;
                color: {COLOR_BLACK_100};
            }}
            QPushButton:checked {{
                background-color: {COLOR_BLACK_50};
                color: {COLOR_BLACK_950};
                font-weight: 700;
                border: 1px solid {COLOR_BLACK_50};
            }}
        """

    def _filter_pill_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: #141414;
                border: 1px solid {COLOR_BLACK_800};
                color: {COLOR_BLACK_400};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #222222;
                color: {COLOR_BLACK_100};
            }}
            QPushButton:checked {{
                background-color: {COLOR_BLACK_50};
                color: {COLOR_BLACK_950};
                font-weight: 700;
                border: 1px solid {COLOR_BLACK_50};
            }}
        """

    def _create_compact_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #141414;
                border: 1px solid {COLOR_BLACK_800};
                border-radius: 6px;
                padding: 4px 6px;
            }}
            QFrame:hover {{
                border-color: {COLOR_BLACK_600};
                background-color: #1c1c1c;
            }}
        """)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(1)

        header_row = QHBoxLayout()
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"color: {COLOR_BLACK_400}; font-size: 10px; font-weight: 600;")
        header_row.addWidget(lbl_t)
        header_row.addStretch()

        lbl_pct = QLabel("0%")
        lbl_pct.setStyleSheet(f"""
            color: {COLOR_BLACK_300};
            background-color: #222222;
            font-size: 9px;
            font-weight: 700;
            padding: 1px 4px;
            border-radius: 3px;
        """)
        card.lbl_pct = lbl_pct
        header_row.addWidget(lbl_pct)
        lo.addLayout(header_row)

        lbl_m = QLabel("0 B")
        lbl_m.setStyleSheet(f"color: {COLOR_BLACK_50}; font-size: 13px; font-weight: 700;")
        card.lbl_main = lbl_m
        lo.addWidget(lbl_m)

        lbl_s = QLabel("0 archivos")
        lbl_s.setStyleSheet(f"color: {COLOR_BLACK_500}; font-size: 9px;")
        card.lbl_sub = lbl_s
        lo.addWidget(lbl_s)

        return card

    def _toggle_metrics_panel(self):
        visible = not self.metrics_container.isVisible()
        self.metrics_container.setVisible(visible)
        arrow = "▲" if visible else "▼"
        self.btn_toggle_metrics.setText(f"📊 Estadísticas Detalladas {arrow}")

    # ==================== DEVICE CONNECTION LIFECYCLE ====================

    def set_device_context(self, adb_bin: Optional[str], serial: Optional[str], device_name: str):
        """Called when a live device is connected and authorized."""
        if not serial:
            self.clear_device_context()
            return

        is_new_device = (serial != self.serial)
        self.adb_bin = adb_bin
        self.serial = serial
        self.device_name = "".join(c for c in device_name if c.isalnum() or c in ("-", "_")).strip() or "dispositivo"

        full_dest = os.path.join(self.output_root_dir, self.device_name)
        self.lbl_target_info.setText(f"Destino directo: {full_dest}")
        self.lbl_device_badge.setText(f"● {self.device_name} ({self.serial})")
        self.lbl_device_badge.setStyleSheet(f"""
            background-color: #0c2010;
            color: {COLOR_SUCCESS};
            border: 1px solid {COLOR_SUCCESS};
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: bold;
        """)

        # If on live mode, show content stack
        if not self.is_historical_mode:
            self.stack.setCurrentIndex(1)

        # If new device connected, start fresh detection without reusing old data
        if is_new_device:
            self.table_model.clear()
            self.current_scan = None
            self.active_session_id = None
            self.lbl_summary_hero.setText("Analizando...")
            self.lbl_summary_sub.setText("Iniciando escaneo del nuevo dispositivo...")
            self.trigger_scan()

    def clear_device_context(self):
        """Called when active device is unplugged or disconnected."""
        self.adb_bin = None
        self.serial = None
        self.device_name = "Dispositivo"
        self.lbl_device_badge.setText("Sin Dispositivo")
        self.lbl_device_badge.setStyleSheet(f"""
            background-color: #1a1a1a;
            color: {COLOR_BLACK_400};
            border: 1px solid {COLOR_BLACK_800};
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: bold;
        """)

        # Switch to waiting screen if in live mode
        if not self.is_historical_mode:
            self.current_scan = None
            self.active_session_id = None
            self.table_model.clear()
            self.stack.setCurrentIndex(0)

    # ==================== MODE SWITCHING (LIVE vs HISTORY) ====================

    def _select_live_mode(self):
        self.is_historical_mode = False
        self.btn_mode_live.setChecked(True)
        self.btn_mode_history.setChecked(False)
        self.combo_history.setVisible(False)
        self.btn_delete_history.setVisible(False)
        self.btn_rescan.setVisible(True)

        if self.serial:
            self.stack.setCurrentIndex(1)
            # Re-fetch latest session for active serial if available
            latest = self.db.get_latest_session_for_serial(self.serial)
            if latest:
                self.active_session_id = latest.session_id
                self._update_ui_from_session(latest)
        else:
            self.stack.setCurrentIndex(0)

    def _select_history_mode(self):
        self.is_historical_mode = True
        self.btn_mode_live.setChecked(False)
        self.btn_mode_history.setChecked(True)
        self.combo_history.setVisible(True)
        self.btn_delete_history.setVisible(True)
        self.btn_rescan.setVisible(False)

        self._refresh_history_combo()
        self.stack.setCurrentIndex(1)

    def _refresh_history_combo(self):
        sessions = self.db.list_sessions()
        self.combo_history.blockSignals(True)
        self.combo_history.clear()

        if not sessions:
            self.combo_history.addItem("(Sin escaneos históricos guardados)", None)
            self.table_model.clear()
            self.lbl_summary_hero.setText("0 B")
            self.lbl_summary_sub.setText("No hay escaneos guardados en el historial")
        else:
            for s in sessions:
                label = f"{s.device_name} — {s.scanned_at} ({s.total_size_formatted}, {s.total_files:,} arch.)"
                self.combo_history.addItem(label, s.session_id)
            # Load first session
            first_id = sessions[0].session_id
            self.active_session_id = first_id
            self._update_ui_from_session(sessions[0])

        self.combo_history.blockSignals(False)

    def _on_history_session_selected(self, index: int):
        session_id = self.combo_history.currentData()
        if not session_id:
            return
        session = self.db.get_session(session_id)
        if session:
            self.active_session_id = session.session_id
            self.device_name = session.device_name
            self._update_ui_from_session(session)

    def _delete_current_history_session(self):
        session_id = self.combo_history.currentData()
        if not session_id:
            return
        confirm = QMessageBox.question(
            self,
            "Eliminar Escaneo Histórico",
            "¿Desea eliminar este registro histórico y sus archivos indexados?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_session(session_id)
            self._refresh_history_combo()

    # ==================== SCAN EXECUTION & STREAMING ====================

    def trigger_scan(self):
        if not self.serial:
            return

        self.bar_distribution.setRange(0, 0)  # Indeterminate animation
        self.bar_distribution.setFormat("Iniciando escaneo incremental de archivos...")
        self.btn_rescan.setEnabled(False)

        profile_id = self.combo_profile.currentData() or "all"

        worker = ScanWorker(
            adb_bin=self.adb_bin,
            serial=self.serial,
            device_name=self.device_name,
            profile_id=profile_id,
            parent=self
        )
        worker.status_sig.connect(lambda msg: self.bar_distribution.setFormat(msg))
        worker.finished_sig.connect(self._on_scan_finished)
        worker.start()

    def _on_scan_finished(self, result: ScanResult):
        self.current_scan = result
        self.active_session_id = result.session_id
        self.btn_rescan.setEnabled(True)
        self.bar_distribution.setRange(0, 100)
        self.bar_distribution.setValue(100)
        self.bar_distribution.setFormat(f"✓ Escaneo completado: {result.total_size_formatted} ({result.total_files:,} archivos)")

        session = self.db.get_session(result.session_id)
        if session:
            self._update_ui_from_session(session)

    def _update_ui_from_session(self, session: ScanSessionRecord):
        # Update Hero stats
        self.lbl_summary_hero.setText(session.total_size_formatted)
        self.lbl_summary_sub.setText(f"{session.total_files:,} archivos en {session.device_name}".replace(",", "."))

        # Update Category Cards via fast SQL breakdown
        breakdown = self.db.get_category_breakdown(session.session_id)

        def update_card(card, cat_name):
            cat = breakdown.get(cat_name)
            if cat:
                card.lbl_main.setText(cat["size_formatted"])
                card.lbl_sub.setText(f"{cat['count']:,} archivos".replace(",", "."))
                card.lbl_pct.setText(f"{cat['percentage']:.1f}%")
            else:
                card.lbl_main.setText("0 B")
                card.lbl_sub.setText("0 archivos")
                card.lbl_pct.setText("0%")

        update_card(self.card_videos, CATEGORY_VIDEOS)
        update_card(self.card_docs, CATEGORY_DOCS)
        update_card(self.card_images, CATEGORY_IMAGES)
        update_card(self.card_audios, CATEGORY_AUDIOS)
        update_card(self.card_databases, CATEGORY_DATABASES)
        update_card(self.card_backups, CATEGORY_BACKUPS)

        self._execute_search_query()

    # ==================== FILTERING, SORTING & QUERYING ====================

    def _set_category_filter(self, category: str):
        self.current_category_filter = category
        self.is_top_50_active = False
        self.btn_top50.setChecked(False)
        self._execute_search_query()

    def _toggle_top50(self):
        self.is_top_50_active = self.btn_top50.isChecked()
        if self.is_top_50_active:
            # Uncheck category filters
            for btn in self.filter_buttons.values():
                btn.setChecked(False)
        else:
            self.filter_buttons["Todos"].setChecked(True)
            self.current_category_filter = "Todos"
        self._execute_search_query()

    def _on_sort_changed(self):
        self.current_sort = self.combo_sort.currentData() or "size_desc"
        self._execute_search_query()

    def _execute_search_query(self):
        """Executes instant indexed query without blocking UI thread."""
        if not self.active_session_id:
            self.table_model.clear()
            self.lbl_table_status.setText("Sin datos.")
            self.lbl_cumulative_size.setText("")
            return

        query_text = self.search_input.text().strip()

        if self.is_top_50_active:
            items = self.db.get_top_largest_files(self.active_session_id, limit=50)
            cnt = len(items)
            total_sz = sum(it.size_bytes for it in items)
            self.table_model.set_items(items, total_count=cnt, total_bytes=total_sz)
            self.lbl_table_status.setText(f"Mostrando los 50 archivos más pesados del dispositivo.")
            self.lbl_cumulative_size.setText(f"Tamaño acumulado: {format_bytes(total_sz)}")
            return

        # Regular filtered & sorted query
        cnt, total_sz = self.db.count_and_sum_files(
            self.active_session_id,
            category=self.current_category_filter,
            search_query=query_text
        )

        # Retrieve first 10,000 items into virtual model (handles fast scrolling without RAM spikes)
        items = self.db.query_files(
            self.active_session_id,
            category=self.current_category_filter,
            search_query=query_text,
            sort_by=self.current_sort,
            limit=10000,
            offset=0
        )

        self.table_model.set_items(items, total_count=cnt, total_bytes=total_sz)

        # Status text
        filter_desc = f"Filtro: {self.current_category_filter}" if self.current_category_filter != "Todos" else "Todos los archivos"
        if query_text:
            filter_desc += f" • Búsqueda: '{query_text}'"

        if cnt > 10000:
            self.lbl_table_status.setText(f"Mostrando primeros 10.000 de {cnt:,} archivos ({filter_desc}).".replace(",", "."))
        else:
            self.lbl_table_status.setText(f"Mostrando {cnt:,} archivos ({filter_desc}).".replace(",", "."))

        self.lbl_cumulative_size.setText(f"Tamaño acumulado: {format_bytes(total_sz)}")

    # ==================== EXTRACTION ====================

    def _open_results_folder(self):
        target = os.path.abspath(os.path.join(self.output_root_dir, self.device_name))
        os.makedirs(target, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(target)
        else:
            import subprocess
            cmd = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([cmd, target])

    def _start_extraction(self):
        if not self.active_session_id:
            QMessageBox.warning(self, "Sin Contenido", "No hay archivos analizados para extraer.")
            return

        # Check if rows are explicitly selected in table
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if selected_indexes:
            items_to_extract = [self.table_model.get_item(idx.row()) for idx in selected_indexes]
            items_to_extract = [it for it in items_to_extract if it is not None]
        else:
            # Extract all currently filtered items directly from database
            query_text = self.search_input.text().strip()
            items_to_extract = self.db.get_all_items_for_extraction(
                self.active_session_id,
                category=self.current_category_filter,
                search_query=query_text
            )

        if not items_to_extract:
            QMessageBox.warning(self, "Sin Selección", "No se encontraron archivos en la vista actual para extraer.")
            return

        total_bytes = sum(i.size_bytes for i in items_to_extract)
        dest_folder = os.path.abspath(os.path.join(self.output_root_dir, self.device_name))

        confirm = QMessageBox.question(
            self,
            "Confirmar Extracción Directa",
            f"¿Desea extraer {len(items_to_extract):,} archivo(s) ({format_bytes(total_bytes)})?\n\n"
            f"Destino en disco:\n{dest_folder}\n\n"
            "Se mantendrá la estructura interna de WhatsApp sin crear carpetas adicionales.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        from PySide6.QtWidgets import QProgressDialog
        prog = QProgressDialog("Iniciando extracción...", "Cancelar", 0, len(items_to_extract), self)
        prog.setWindowTitle("Extrayendo WhatsApp Media")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)

        self.extractor_worker = DirectExtractorWorker(
            items=items_to_extract,
            device_name=self.device_name,
            adb_bin=self.adb_bin,
            serial=self.serial,
            base_results_dir=self.output_root_dir,
            parent=self
        )

        def on_prog(cur, tot, fn):
            prog.setValue(cur)
            prog.setLabelText(f"Copiando ({cur:,}/{tot:,}): {fn}")

        prog.canceled.connect(self.extractor_worker.cancel)
        self.extractor_worker.progress_sig.connect(on_prog)

        def on_fin(ok, path, cnt):
            prog.close()
            if ok:
                msg = QMessageBox(self)
                msg.setWindowTitle("Extracción Completada")
                msg.setText(f"✓ Se extrajeron {cnt:,} archivos exitosamente en:\n{path}")
                btn_open = msg.addButton("Abrir Carpeta", QMessageBox.ButtonRole.ActionRole)
                msg.addButton(QMessageBox.StandardButton.Ok)
                msg.exec()
                if msg.clickedButton() == btn_open:
                    self._open_results_folder()
            else:
                QMessageBox.warning(self, "Extracción Cancelada", f"Se extrajeron {cnt:,} archivos antes de cancelar.")

        self.extractor_worker.finished_sig.connect(on_fin)
        self.extractor_worker.start()
