"""
Design System and Themes for wab_gui.
Palette based on Danube (Kigen.design) with Dark Carbon / iOS minimalism.
"""

# Danube Color Tokens
COLOR_DANUBE_50  = "#eaf1fc"
COLOR_DANUBE_100 = "#cedff8"
COLOR_DANUBE_200 = "#9ec4f2"
COLOR_DANUBE_300 = "#6babec"
COLOR_DANUBE_400 = "#4891d3"
COLOR_DANUBE_500 = "#3274ae"
COLOR_DANUBE_600 = "#1b5483"
COLOR_DANUBE_700 = "#103d62"
COLOR_DANUBE_800 = "#082945"
COLOR_DANUBE_900 = "#041728"
COLOR_DANUBE_950 = "#010b18"

# Status Colors (soft/pastel dark carbon)
COLOR_SUCCESS = "#48c774"
COLOR_WARNING = "#e5c07b"
COLOR_ERROR   = "#e06c75"
COLOR_MUTED   = "#7b93a8"

MAIN_STYLESHEET = f"""
/* Global Reset & Base */
QWidget {{
    background-color: {COLOR_DANUBE_950};
    color: {COLOR_DANUBE_50};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
    selection-background-color: {COLOR_DANUBE_600};
    selection-color: {COLOR_DANUBE_50};
}}

/* Main Window */
QMainWindow {{
    background-color: {COLOR_DANUBE_950};
}}

/* Cards & Containers (iOS / Instagram grouped style) */
QFrame#card, QWidget#card {{
    background-color: {COLOR_DANUBE_900};
    border: 1px solid {COLOR_DANUBE_800};
    border-radius: 12px;
    padding: 14px;
}}

QFrame#cardElevated {{
    background-color: {COLOR_DANUBE_800};
    border: 1px solid {COLOR_DANUBE_700};
    border-radius: 10px;
    padding: 10px;
}}

/* Headings */
QLabel#h1 {{
    font-size: 18px;
    font-weight: 700;
    color: {COLOR_DANUBE_50};
}}

QLabel#h2 {{
    font-size: 15px;
    font-weight: 600;
    color: {COLOR_DANUBE_100};
}}

QLabel#subtitle {{
    font-size: 12px;
    color: {COLOR_MUTED};
}}

/* Inputs & Form controls */
QLineEdit, QComboBox, QSpinBox, QDateEdit {{
    background-color: {COLOR_DANUBE_900};
    border: 1px solid {COLOR_DANUBE_800};
    border-radius: 8px;
    padding: 7px 10px;
    color: {COLOR_DANUBE_50};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {COLOR_DANUBE_400};
    background-color: {COLOR_DANUBE_800};
}}

QLineEdit:disabled, QComboBox:disabled {{
    background-color: {COLOR_DANUBE_950};
    color: {COLOR_MUTED};
    border-color: {COLOR_DANUBE_900};
}}

/* Buttons */
QPushButton {{
    background-color: {COLOR_DANUBE_700};
    border: 1px solid {COLOR_DANUBE_600};
    color: {COLOR_DANUBE_50};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLOR_DANUBE_600};
    border-color: {COLOR_DANUBE_500};
}}

QPushButton:pressed {{
    background-color: {COLOR_DANUBE_800};
}}

QPushButton:disabled {{
    background-color: {COLOR_DANUBE_900};
    color: {COLOR_MUTED};
    border-color: {COLOR_DANUBE_800};
}}

/* Primary Action Button (Call-To-Action) */
QPushButton#primaryBtn {{
    background-color: {COLOR_DANUBE_500};
    border: 1px solid {COLOR_DANUBE_400};
    color: #ffffff;
    font-weight: 600;
    border-radius: 8px;
    padding: 9px 18px;
}}

QPushButton#primaryBtn:hover {{
    background-color: {COLOR_DANUBE_400};
    border-color: {COLOR_DANUBE_300};
}}

QPushButton#primaryBtn:pressed {{
    background-color: {COLOR_DANUBE_600};
}}

/* Tab Widget (iOS segmented style) */
QTabWidget::pane {{
    border: 1px solid {COLOR_DANUBE_800};
    background-color: {COLOR_DANUBE_950};
    border-radius: 12px;
    top: -1px;
    padding: 8px;
}}

QTabBar::tab {{
    background: {COLOR_DANUBE_900};
    color: {COLOR_DANUBE_200};
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid {COLOR_DANUBE_800};
    border-bottom: none;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background: {COLOR_DANUBE_800};
    color: {COLOR_DANUBE_50};
    border-color: {COLOR_DANUBE_600};
}}

QTabBar::tab:hover:!selected {{
    background: {COLOR_DANUBE_800};
    color: {COLOR_DANUBE_100};
}}

/* Scrollbars (Minimalist) */
QScrollBar:vertical {{
    background: {COLOR_DANUBE_950};
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_DANUBE_700};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_DANUBE_500};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Checkboxes */
QCheckBox {{
    color: {COLOR_DANUBE_100};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {COLOR_DANUBE_700};
    background-color: {COLOR_DANUBE_900};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_DANUBE_500};
    border-color: {COLOR_DANUBE_400};
}}

/* Progress Bar */
QProgressBar {{
    background-color: {COLOR_DANUBE_900};
    border: 1px solid {COLOR_DANUBE_800};
    border-radius: 6px;
    text-align: center;
    color: {COLOR_DANUBE_50};
    font-size: 11px;
    height: 14px;
}}

QProgressBar::chunk {{
    background-color: {COLOR_DANUBE_500};
    border-radius: 5px;
}}

/* Tooltips */
QToolTip {{
    background-color: {COLOR_DANUBE_800};
    color: {COLOR_DANUBE_50};
    border: 1px solid {COLOR_DANUBE_600};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""
