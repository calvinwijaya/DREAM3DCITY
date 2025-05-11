import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QLabel, QHBoxLayout
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt
from function.tab1_reconstruct import ReconstructTab
from function.tab2_editvisualize import VisualizeTab
from function.tab3_semantic import SemanticTab
from function.tab4_manual_semantic import ManualSemanticTab
from function.translate_obj import OBJTranslatorGUI
from function.tab5_mergecityjson import MergeCityJSON

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
        self.tabs.addTab(ReconstructTab(), "3D Reconstruction")
        self.tabs.addTab(VisualizeTab(), "3D Visualize")
        self.tabs.addTab(SemanticTab(), "CityJSON Semantic") 
        self.tabs.addTab(ManualSemanticTab(), "Manual Semantic")
        self.tabs.addTab(OBJTranslatorGUI(), "OBJ Translator")
        self.tabs.addTab(MergeCityJSON(), "Merge CityJSON")
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