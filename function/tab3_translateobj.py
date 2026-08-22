from PyQt6.QtWidgets import QWidget, QTabWidget, QVBoxLayout

# Import the upgraded PyQt6 Sub-tabs
from function.obj2utmtranslator import OBJ2UTMTranslatorGUI
from function.obj2localtranslator import OBJ2LocalTranslatorGUI
from function.obj2wgstranslator import OBJ2WGSTranslatorGUI
from function.objmerge import OBJMerger
from function.tab3_semantic import SemanticTab

class OBJTranslatorGUI(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #E2E8F0; background: #FFFFFF; border-radius: 8px; }
            QTabBar::tab { background: #F8FAFC; color: #64748B; padding: 8px 16px; margin-right: 2px; border-radius: 4px; border: 1px solid transparent; }
            QTabBar::tab:selected { background: #E0E7FF; color: #1E40AF; font-weight: bold; border: 1px solid #BFDBFE; }
            QTabBar::tab:hover:!selected { background: #F1F5F9; }
        """)

        # Add the completed PyQt6 Tabs
        self.sub_tabs.addTab(OBJ2UTMTranslatorGUI(), "Translate Local → UTM")
        self.sub_tabs.addTab(OBJ2LocalTranslatorGUI(), "Translate UTM → Local")
        self.sub_tabs.addTab(OBJ2WGSTranslatorGUI(), "Translate UTM → WGS84")
        self.sub_tabs.addTab(OBJMerger(), "Merge OBJs")
        self.sub_tabs.addTab(SemanticTab(), "OBJ Semantic Mapping")

        layout.addWidget(self.sub_tabs)
        self.setLayout(layout)