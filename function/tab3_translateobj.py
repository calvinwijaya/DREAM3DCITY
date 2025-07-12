from PyQt5.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from function.obj2utmtranslator import OBJ2UTMTranslatorGUI
from function.obj2localtranslator import OBJ2LocalTranslatorGUI
from function.obj2wgstranslator import OBJ2WGSTranslatorGUI
from function.objmerge import OBJMerger
from function.tab3_semantic import SemanticTab

class OBJTranslatorGUI(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        sub_tabs = QTabWidget()
        sub_tabs.addTab(OBJ2UTMTranslatorGUI(), "Translate Local→UTM")
        sub_tabs.addTab(OBJ2LocalTranslatorGUI(), "Translate UTM→Local")
        sub_tabs.addTab(OBJ2WGSTranslatorGUI(), "Translate UTM→WGS84")
        sub_tabs.addTab(OBJMerger(), "Merge OBJs")
        sub_tabs.addTab(SemanticTab(), "OBJ Semantic Mapping")

        layout.addWidget(sub_tabs)
        self.setLayout(layout)
