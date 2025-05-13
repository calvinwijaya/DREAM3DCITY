import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog, QVBoxLayout,
    QSlider, QLineEdit, QMessageBox, QHBoxLayout, QPlainTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from function.semantic_mapping import *

class SemanticTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def _bold_label(self, text):
        label = QLabel(text)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        return label

    def init_ui(self):
        layout = QVBoxLayout()

        # OBJ source: file or folder
        layout.addWidget(self._bold_label("Input OBJ"))
        self.input_obj = QLineEdit()
        self.btn_browse_obj = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.input_obj)
        row1.addWidget(self.btn_browse_obj)
        layout.addLayout(row1)

        # BO GeoJSON
        layout.addWidget(self._bold_label("Building Outline (BO) GeoJSON"))
        self.input_geojson = QLineEdit()
        self.btn_browse_geojson = QPushButton("Browse")
        row2 = QHBoxLayout()
        row2.addWidget(self.input_geojson)
        row2.addWidget(self.btn_browse_geojson)
        layout.addLayout(row2)

        # Process button
        self.btn_process = QPushButton("Process")
        self.btn_process.setFont(QFont("Arial", 10, QFont.Bold))
        self.btn_process.setStyleSheet("padding: 8px;")
        layout.addWidget(self.btn_process)

        # Log output
        layout.addWidget(self._bold_label("Log Output"))
        self.log_window = QPlainTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(self.log_window)

        self.setLayout(layout)

        # Connections
        self.btn_browse_obj.clicked.connect(self.browse_obj)
        self.btn_browse_geojson.clicked.connect(self.browse_geojson)
        self.btn_process.clicked.connect(self.process_files)

    def browse_obj(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OBJ File or Folder", "", "OBJ files (*.obj)")
        if not path:
            path = QFileDialog.getExistingDirectory(self, "Or Select Directory")
        if path:
            self.input_obj.setText(path)

    def browse_geojson(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select GeoJSON File", "", "GeoJSON files (*.geojson *.json)")
        if path:
            self.input_geojson.setText(path)

    def process_files(self):
        self.log_window.clear()
        obj_input = self.input_obj.text().strip()
        geojson_path = self.input_geojson.text().strip()

        if not all([obj_input, geojson_path]):
            QMessageBox.warning(self, "Missing Input", "Please fill in all paths.")
            return

        try:
            # Redirect print to log window
            class QTextStream:
                def write(_, text):
                    self.log_window.appendPlainText(text.rstrip())

            old_stdout = sys.stdout
            sys.stdout = QTextStream()

            if os.path.isfile(obj_input) and obj_input.endswith('.obj'):
                colorizer = BuildingColorizer(Path(obj_input).parent, geojson_path)
                colorizer.process_building(Path(obj_input))
                colorizer.print_summary()
            elif os.path.isdir(obj_input):
                colorizer = BuildingColorizer(obj_input, geojson_path)
                colorizer.process_all_buildings()
            else:
                self.log_window.appendPlainText("Invalid OBJ input. Must be .obj file or directory.")

            sys.stdout = old_stdout
            QMessageBox.information(self, "Done", "Processing completed.")

        except Exception as e:
            sys.stdout = old_stdout
            QMessageBox.critical(self, "Error", str(e))
