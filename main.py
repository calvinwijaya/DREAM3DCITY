import sys
import base64
import types
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QLabel, QHBoxLayout, QStackedLayout, QScrollArea
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt
from cryptography.fernet import Fernet

# ========== FUNGSI DEKRIPSI IN-MEMORY ==========
def load_key():
    encoded = "U3IzSXBEQ1pWd1lSUDZNODBiOTNGWjhXZjFsaC04TDItZHRfc3dnajl3RT0="
    return base64.b64decode(encoded)

def dynamic_import_class(file_path: str, class_name: str):
    key = load_key()
    fernet = Fernet(key)
    with open(file_path, "rb") as f:
        decrypted_code = fernet.decrypt(f.read())
    namespace = {"__name__": "__main__"}
    exec(decrypted_code, namespace)
    return namespace[class_name]

def dynamic_import_file(file_path: str, module_name: str):
    key = load_key()
    fernet = Fernet(key)
    with open(file_path, "rb") as f:
        decrypted_code = fernet.decrypt(f.read())
    namespace = {"__name__": module_name}
    exec(decrypted_code, namespace)
    sys.modules[module_name] = types.ModuleType(module_name)
    sys.modules[module_name].__dict__.update(namespace)
# ===============================================

class LockedTabWrapper(QWidget):
    def __init__(self, tab_widget: QWidget):
        super().__init__()
        self.tab_widget = tab_widget
        self.disable_all_widgets(tab_widget)
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

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        self.tabs = QTabWidget()

        # === Decrypt modul utama ===
        dynamic_import_file("encrypted_function/obj2utmtranslator.py.enc", "obj2utmtranslator")
        dynamic_import_file("encrypted_function/obj2localtranslator.py.enc", "obj2localtranslator")
        dynamic_import_file("encrypted_function/obj2wgstranslator.py.enc", "obj2wgstranslator")
        dynamic_import_file("encrypted_function/objmerge.py.enc", "objmerge")
        dynamic_import_file("encrypted_function/obj2gml/semantic_mapping.py.enc", "obj2gml.semantic_mapping")

        # Registrasi sebagai function.*
        sys.modules["function.obj2utmtranslator"] = sys.modules["obj2utmtranslator"]
        sys.modules["function.obj2localtranslator"] = sys.modules["obj2localtranslator"]
        sys.modules["function.obj2wgstranslator"] = sys.modules["obj2wgstranslator"]
        sys.modules["function.objmerge"] = sys.modules["objmerge"]

        # Registrasi semantic_mapping
        if "function.obj2gml" not in sys.modules:
            sys.modules["function.obj2gml"] = types.ModuleType("function.obj2gml")
            sys.modules["function.obj2gml"].__path__ = []
        sys.modules["function.obj2gml.semantic_mapping"] = sys.modules["obj2gml.semantic_mapping"]

        # === tab3_semantic (depends on semantic_mapping)
        dynamic_import_file("encrypted_function/tab3_semantic.py.enc", "tab3_semantic")
        sys.modules["function.tab3_semantic"] = sys.modules["tab3_semantic"]

        # === Dummy obj2gml package (agar absolute import tidak error)
        if "obj2gml" not in sys.modules:
            dummy_pkg = types.ModuleType("obj2gml")
            dummy_pkg.__path__ = []
            sys.modules["obj2gml"] = dummy_pkg

        # === Dekripsi semua submodul obj2gml KECUALI file CLI
        obj2gml_modules = [
            "attribute_gen", "cacheHandling", "copyNrename", "findFile", "lod2merge",
            "obj2gml_batchservice", "semantic_mapping", "transformobj"
        ]
        for mod in obj2gml_modules:
            path = f"encrypted_function/obj2gml/{mod}.py.enc"
            name = f"obj2gml.{mod}"
            dynamic_import_file(path, name)
            sys.modules[f"function.obj2gml.{mod}"] = sys.modules[name]

        # === obj2cityjson package
        obj2cityjson_pkg = types.ModuleType("obj2cityjson")
        obj2cityjson_pkg.__path__ = []
        sys.modules["obj2cityjson"] = obj2cityjson_pkg

        for mod in ["tojson", "mergeobj", "separator", "json2gml", "color"]:
            path = f"encrypted_function/obj2cityjson/{mod}.py.enc"
            name = f"obj2cityjson.{mod}"
            dynamic_import_file(path, name)
            sys.modules[f"function.obj2cityjson.{mod}"] = sys.modules[name]

        # === Load semua tab
        ReconstructTab = dynamic_import_class("encrypted_function/tab1_reconstruct.py.enc", "ReconstructTab")
        OBJTranslatorGUI = dynamic_import_class("encrypted_function/tab3_translateobj.py.enc", "OBJTranslatorGUI")
        GoRunner = dynamic_import_class("encrypted_function/tab4_gorunner.py.enc", "GoRunner")
        MergeCityJSON = dynamic_import_class("encrypted_function/tab5_mergecityjson.py.enc", "MergeCityJSON")
        Obj2GMLTab = dynamic_import_class("encrypted_function/tab6_obj2gml.py.enc", "Obj2GML")

        self.tabs.addTab(ScrollableTabWrapper(ReconstructTab()), "3D Reconstruction")
        self.tabs.addTab(ScrollableTabWrapper(OBJTranslatorGUI()), "OBJ Tools")
        self.tabs.addTab(ScrollableTabWrapper(GoRunner()), "OBJ to 3D City")
        self.tabs.addTab(ScrollableTabWrapper(MergeCityJSON()), "Merge CityJSON")
        self.tabs.addTab(ScrollableTabWrapper(Obj2GMLTab()), "OBJ ➝ CityGML (Batch)")

        central_layout.addWidget(self.tabs)

        # === Footer ===
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
