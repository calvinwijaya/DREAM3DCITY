import os
import sys
import time
import io

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout,
    QHBoxLayout, QLineEdit, QTextEdit, QMessageBox, QGroupBox,
    QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Import your custom external script
from function.obj2gml.semantic_mapping import BuildingColorizer


class StreamInterceptor(io.StringIO):
    """Safely catches print() statements from external scripts and emits them as signals."""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def write(self, text):
        if text.strip():  # Ignore empty newlines to keep the log clean
            self.signal.emit(text.strip())


class SemanticWorker(QThread):
    """Background worker to run the heavy semantic mapping without freezing the GUI."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, float)

    def __init__(self, obj_dir, geojson_path):
        super().__init__()
        self.obj_dir = obj_dir
        self.geojson_path = geojson_path

    def run(self):
        start_time = time.perf_counter()
        old_stdout = sys.stdout  # Save the original standard output

        try:
            # 1. Intercept prints from the external script
            interceptor = StreamInterceptor(self.log_signal)
            sys.stdout = interceptor
            
            # 2. Run the heavy processing
            self.log_signal.emit("🚀 Starting Semantic Mapping Process...")
            colorizer = BuildingColorizer(self.obj_dir, self.geojson_path)
            colorizer.process_all_buildings()
            
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(True, "Semantic mapping completed successfully.", elapsed)

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(False, str(e), elapsed)

        finally:
            # 3. ALWAYS restore standard output, even if it crashes
            sys.stdout = old_stdout


class SemanticTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def _bold_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 600; color: #334155;")
        return lbl

    def _create_btn(self, text, primary=False):
        btn = QPushButton(text)
        if primary:
            btn.setStyleSheet("""
                QPushButton { background-color: #2563EB; color: white; font-weight: bold; font-size: 14px; padding: 10px; border-radius: 6px; border: none; }
                QPushButton:hover { background-color: #1D4ED8; }
                QPushButton:disabled { background-color: #94A3B8; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px 12px; }
                QPushButton:hover { background-color: #F1F5F9; }
            """)
        return btn

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 1. Input Group
        input_group = QGroupBox("1. Input Data")
        input_layout = QVBoxLayout()
        
        # OBJ input folder
        input_layout.addWidget(self._bold_label("Input OBJ Folder Directory"))
        row1 = QHBoxLayout()
        self.input_obj = QLineEdit()
        self.input_obj.setPlaceholderText("Select the directory containing the OBJ files...")
        self.btn_browse_obj = self._create_btn("Browse")
        self.btn_browse_obj.clicked.connect(self.browse_obj)
        row1.addWidget(self.input_obj)
        row1.addWidget(self.btn_browse_obj)
        input_layout.addLayout(row1)

        input_layout.addSpacing(5)

        # BO GeoJSON
        input_layout.addWidget(self._bold_label("Input BO GeoJSON"))
        row2 = QHBoxLayout()
        self.input_geojson = QLineEdit()
        self.input_geojson.setPlaceholderText("Select the Building Outline GeoJSON file...")
        self.btn_browse_geojson = self._create_btn("Browse")
        self.btn_browse_geojson.clicked.connect(self.browse_geojson)
        row2.addWidget(self.input_geojson)
        row2.addWidget(self.btn_browse_geojson)
        input_layout.addLayout(row2)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 2. Process Button & Progress Bar
        self.btn_process = self._create_btn("Process Semantic Mapping", primary=True)
        self.btn_process.clicked.connect(self.start_processing)
        layout.addWidget(self.btn_process)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #E2E8F0; border: none; } QProgressBar::chunk { background-color: #2563EB; }")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 3. Log Output
        layout.addWidget(self._bold_label("Execution Log"))
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A; color: #F8FAFC;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12px; border-radius: 6px; padding: 8px; border: 1px solid #334155;
            }
        """)
        layout.addWidget(self.log_console)

    def log(self, message):
        self.log_console.append(message)

    def browse_obj(self):
        path = QFileDialog.getExistingDirectory(self, "Select Directory Containing OBJ Files")
        if path:
            self.input_obj.setText(path)
            self.log(f"📁 OBJ Directory selected: {path}")

    def browse_geojson(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select GeoJSON File", "", "GeoJSON files (*.geojson *.json)")
        if path:
            self.input_geojson.setText(path)
            self.log(f"🌍 GeoJSON selected: {path}")

    def start_processing(self):
        obj_dir = self.input_obj.text().strip()
        geojson_path = self.input_geojson.text().strip()

        if not obj_dir or not os.path.isdir(obj_dir):
            QMessageBox.warning(self, "Missing Input", "Please select a valid directory containing OBJ files.")
            return
            
        if not geojson_path or not os.path.exists(geojson_path):
            QMessageBox.warning(self, "Missing Input", "Please select a valid GeoJSON file.")
            return

        # UI State Updates
        self.btn_process.setEnabled(False)
        self.btn_process.setText("Mapping Semantics...")
        self.progress_bar.setVisible(True)
        self.log_console.clear()

        # Start Background Worker
        self.worker = SemanticWorker(obj_dir, geojson_path)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_processing_finished)
        self.worker.start()

    def on_processing_finished(self, success, message, elapsed):
        self.btn_process.setEnabled(True)
        self.btn_process.setText("Process Semantic Mapping")
        self.progress_bar.setVisible(False)
        
        if success:
            finish_msg = f"✅ {message} Completed in {elapsed:.2f} seconds."
            self.log(finish_msg)
            QMessageBox.information(self, "Process Complete", finish_msg)
        else:
            self.log(f"❌ Process failed:\n{message}")
            QMessageBox.critical(self, "Process Failed", f"An error occurred during mapping:\n{message}")