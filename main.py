import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QLabel, QHBoxLayout, QStackedLayout, QScrollArea
)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt

from function.tab1_reconstruct import ReconstructTab
from function.tab2_editvisualize import VisualizeTab
from function.tab3_translateobj import OBJTranslatorGUI
from function.tab4_gorunner import GoRunner
from function.tab5_mergecityjson import MergeCityJSON
from function.tab6_obj2gml import Obj2GML


# Global Modern Stylesheet
MODERN_STYLE = """
QMainWindow {
    background-color: #F8FAFC;
}

QWidget {
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    color: #1E293B;
}

/* Tab Bar Styling */
QTabWidget::pane {
    border: 1px solid #E2E8F0;
    background: #FFFFFF;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: #F1F5F9;
    color: #64748B;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
    border: 1px solid #E2E8F0;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    color: #0F172A;
    border-bottom: 2px solid #2563EB;
}

QTabBar::tab:hover:!selected {
    background: #E2E8F0;
    color: #334155;
}

/* Input Fields */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0F172A;
    selection-background-color: #2563EB;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #2563EB;
}

/* Push Buttons */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    color: #334155;
}

QPushButton:hover {
    background-color: #F8FAFC;
    border-color: #94A3B8;
}

QPushButton:pressed {
    background-color: #E2E8F0;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #E2E8F0;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #2563EB;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #2563EB;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #CBD5E1;
    background: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #2563EB;
    border-color: #2563EB;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #F8FAFC;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


class ScrollableTabWrapper(QWidget):
    def __init__(self, content_widget: QWidget):
        super().__init__()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(scroll_area)

        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DREAM 3D CITY")
        self.resize(1080, 640)
        self.setWindowIcon(QIcon("ui/logo.svg"))

        # Root Central Layout
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(16, 16, 16, 12)
        central_layout.setSpacing(12)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.addTab(ScrollableTabWrapper(ReconstructTab()), "3D Reconstruction")
        self.tabs.addTab(ScrollableTabWrapper(VisualizeTab()), "3D Visualize")
        self.tabs.addTab(ScrollableTabWrapper(OBJTranslatorGUI()), "OBJ Tools")
        self.tabs.addTab(ScrollableTabWrapper(GoRunner()), "OBJ to 3D City")
        self.tabs.addTab(ScrollableTabWrapper(MergeCityJSON()), "Merge CityJSON")
        self.tabs.addTab(ScrollableTabWrapper(Obj2GML()), "OBJ to GML")
        central_layout.addWidget(self.tabs)

        # Footer Layout
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(4, 4, 4, 4)

        footer_logo = QLabel()
        footer_logo.setPixmap(
            QPixmap("ui/footer.png").scaledToHeight(36, Qt.TransformationMode.SmoothTransformation)
        )
        footer_logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        footer_text = QLabel("Department of Geodetic Engineering, Faculty of Engineering, Universitas Gadjah Mada")
        footer_text.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 500;")
        footer_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        footer_layout.addWidget(footer_logo)
        footer_layout.addSpacing(8)
        footer_layout.addWidget(footer_text)
        footer_layout.addStretch(1)

        central_layout.addLayout(footer_layout)
        self.setCentralWidget(central_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())