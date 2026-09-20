"""
Design System and Themes for wab_gui.
Palette based on Kigen.design Monochrome Pitch Black & Titanium (--black-50 to --black-950)
with sleek Apple Pro / iOS minimalism.
"""

# Kigen.design Monochrome Pitch Black & Titanium Tokens
COLOR_BLACK_50  = "#ffffff"
COLOR_BLACK_100 = "#f1f1f1"
COLOR_BLACK_200 = "#e1e1e1"
COLOR_BLACK_300 = "#d0d0d0"
COLOR_BLACK_400 = "#bdbdbd"
COLOR_BLACK_500 = "#a7a7a7"
COLOR_BLACK_600 = "#8a8a8a"
COLOR_BLACK_700 = "#6b6b6b"
COLOR_BLACK_800 = "#4b4b4b"
COLOR_BLACK_900 = "#2a2a2a"
COLOR_BLACK_950 = "#010101"

# Backward compatibility aliases for existing imports
COLOR_DANUBE_50  = COLOR_BLACK_50
COLOR_DANUBE_100 = COLOR_BLACK_100
COLOR_DANUBE_200 = COLOR_BLACK_200
COLOR_DANUBE_300 = COLOR_BLACK_300
COLOR_DANUBE_400 = COLOR_BLACK_400
COLOR_DANUBE_500 = COLOR_BLACK_500
COLOR_DANUBE_600 = COLOR_BLACK_600
COLOR_DANUBE_700 = COLOR_BLACK_700
COLOR_DANUBE_800 = COLOR_BLACK_800
COLOR_DANUBE_900 = COLOR_BLACK_900
COLOR_DANUBE_950 = COLOR_BLACK_950

# Semantic Accents & Status (Apple Pro minimal)
COLOR_SUCCESS = "#ffffff"       # Crisp white CTA
COLOR_WARNING = "#d0d0d0"
COLOR_ERROR   = "#ff453a"       # Subtle iOS red for critical alerts
COLOR_MUTED   = COLOR_BLACK_500 # #a7a7a7
COLOR_SURFACE = "#121212"       # Deep card surface
COLOR_BORDER  = COLOR_BLACK_800 # #4b4b4b

MAIN_STYLESHEET = f"""
/* Global Reset & Base */
QWidget {{
    background-color: {COLOR_BLACK_950};
    color: {COLOR_BLACK_50};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
    selection-background-color: {COLOR_BLACK_800};
    selection-color: {COLOR_BLACK_50};
}}

/* Main Window */
QMainWindow {{
    background-color: {COLOR_BLACK_950};
}}

/* Cards & Containers (iOS / Apple Pro minimal) */
QFrame#card, QWidget#card {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BLACK_900};
    border-radius: 12px;
    padding: 12px;
}}

QFrame#card:hover {{
    border-color: {COLOR_BLACK_800};
}}

QFrame#heroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a1a, stop:1 #0d0d0d);
    border: 1px solid {COLOR_BLACK_800};
    border-radius: 14px;
    padding: 16px;
}}

QFrame#cardElevated {{
    background-color: #1a1a1a;
    border: 1px solid {COLOR_BLACK_800};
    border-radius: 10px;
    padding: 10px;
}}

/* Headings */
QLabel#h1 {{
    font-size: 18px;
    font-weight: 700;
    color: {COLOR_BLACK_50};
}}

QLabel#h2 {{
    font-size: 15px;
    font-weight: 600;
    color: {COLOR_BLACK_100};
}}

QLabel#subtitle {{
    font-size: 12px;
    color: {COLOR_MUTED};
}}

/* Inputs & Form controls */
QLineEdit, QComboBox, QSpinBox, QDateEdit {{
    background-color: #141414;
    border: 1px solid {COLOR_BLACK_800};
    border-radius: 8px;
    padding: 7px 12px;
    color: {COLOR_BLACK_50};
    font-size: 13px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {COLOR_BLACK_500};
    background-color: #1a1a1a;
}}

QLineEdit:disabled, QComboBox:disabled {{
    background-color: {COLOR_BLACK_950};
    color: {COLOR_MUTED};
    border-color: {COLOR_BLACK_900};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}}

/* Standard Buttons */
QPushButton {{
    background-color: #181818;
    border: 1px solid {COLOR_BLACK_800};
    color: {COLOR_BLACK_200};
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLOR_BLACK_900};
    border-color: {COLOR_BLACK_600};
    color: {COLOR_BLACK_50};
}}

QPushButton:pressed {{
    background-color: #101010;
}}

QPushButton:disabled {{
    background-color: #101010;
    color: {COLOR_BLACK_700};
    border-color: {COLOR_BLACK_900};
}}

/* Primary Action Button (Apple Pro CTA: Solid Crisp White on Black) */
QPushButton#primaryBtn {{
    background-color: {COLOR_BLACK_50};
    border: 1px solid {COLOR_BLACK_50};
    color: {COLOR_BLACK_950};
    font-weight: 700;
    border-radius: 8px;
    padding: 9px 20px;
    font-size: 13px;
}}

QPushButton#primaryBtn:hover {{
    background-color: {COLOR_BLACK_200};
    border-color: {COLOR_BLACK_200};
}}

QPushButton#primaryBtn:pressed {{
    background-color: {COLOR_BLACK_400};
    border-color: {COLOR_BLACK_400};
}}

/* Tab Widget (iOS segmented style) */
QTabWidget::pane {{
    border: 1px solid {COLOR_BLACK_900};
    background-color: {COLOR_BLACK_950};
    border-radius: 12px;
    top: -1px;
    padding: 8px;
}}

QTabBar::tab {{
    background: #141414;
    color: {COLOR_BLACK_500};
    padding: 8px 18px;
    margin-right: 6px;
    border-radius: 8px;
    border: 1px solid {COLOR_BLACK_900};
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background: {COLOR_BLACK_900};
    color: {COLOR_BLACK_50};
    border-color: {COLOR_BLACK_700};
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    background: #1c1c1c;
    color: {COLOR_BLACK_200};
}}

/* Scrollbars (Minimalist) */
QScrollBar:vertical {{
    background: {COLOR_BLACK_950};
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BLACK_800};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_BLACK_600};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Checkboxes */
QCheckBox {{
    color: {COLOR_BLACK_200};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {COLOR_BLACK_700};
    background-color: #141414;
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_BLACK_50};
    border-color: {COLOR_BLACK_50};
}}

/* Progress Bar */
QProgressBar {{
    background-color: #141414;
    border: 1px solid {COLOR_BLACK_800};
    border-radius: 6px;
    text-align: center;
    color: {COLOR_BLACK_50};
    font-size: 11px;
    font-weight: 600;
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {COLOR_BLACK_300};
    border-radius: 5px;
}}

/* Tooltips */
QToolTip {{
    background-color: #1f1f1f;
    color: {COLOR_BLACK_50};
    border: 1px solid {COLOR_BLACK_700};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""
