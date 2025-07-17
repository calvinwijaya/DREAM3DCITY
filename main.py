import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QLabel, QHBoxLayout, QStackedLayout, QScrollArea
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize
from function.tab1_reconstruct import ReconstructTab
# from function.tab2_editvisualize import VisualizeTab
from function.tab3_translateobj import OBJTranslatorGUI
from function.tab4_gorunner import GoRunner
from function.tab5_mergecityjson import MergeCityJSON
from function.tab6_obj2gml import Obj2GML

class LockedTabWrapper(QWidget):
    def __init__(self, tab_widget: QWidget):
        super().__init__()
        self.tab_widget = tab_widget

        # Disable all child widgets
        self.disable_all_widgets(tab_widget)

        # Layout
        layout = QStackedLayout(self)
        layout.addWidget(tab_widget)
    
    def disable_all_widgets(self, parent_widget):
        for child in parent_widget.findChildren(QWidget):
            child.setDisabled(True)

class ScrollableTabWrapper(QWidget):
    def __init__(self, content_widget: QWidget):
        super().__init__()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DREAM 3D CITY")
        self.resize(900, 800)
        self.setWindowIcon(QIcon("ui/logo.png"))

        # Central widget and layout
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(ScrollableTabWrapper(ReconstructTab()), "3D Reconstruction")
        # self.tabs.addTab(ScrollableTabWrapper(VisualizeTab()), "3D Visualize")
        self.tabs.addTab(ScrollableTabWrapper(OBJTranslatorGUI()), "OBJ Tools")
        self.tabs.addTab(ScrollableTabWrapper(GoRunner()), "OBJ to 3D City")
        self.tabs.addTab(ScrollableTabWrapper(MergeCityJSON()), "Merge CityJSON")
        self.tabs.addTab(ScrollableTabWrapper(Obj2GML()), "OBJ to GML")
        central_layout.addWidget(self.tabs)

        # Footer
        footer_layout = QHBoxLayout()
        footer_logo = QLabel()
        footer_logo.setPixmap(QPixmap("ui/footer.png").scaledToHeight(40, Qt.SmoothTransformation))
        footer_logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        footer_text = QLabel("Geo-AI Team, Department of Geodetic Engineering, Faculty of Engineering, Universitas Gadjah Mada")
        footer_text.setStyleSheet("font-size: 10pt; color: gray;")
        footer_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        footer_layout.addWidget(footer_logo)
        footer_layout.addWidget(footer_text)
        footer_layout.setStretch(1, 1)

        central_layout.addLayout(footer_layout)

        self.setCentralWidget(central_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())