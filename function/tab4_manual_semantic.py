import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog, QVBoxLayout,
    QSlider, QLineEdit, QMessageBox, QHBoxLayout, QPlainTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from function.manual_semantic_helper import *  # Import the helper functions


class ManualSemanticTab(QWidget):
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

        # ===== Input OBJ =====
        layout.addWidget(self._bold_label("Input OBJ File"))
        self.input_obj = QLineEdit()
        self.btn_browse_obj = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.input_obj)
        row1.addWidget(self.btn_browse_obj)
        layout.addLayout(row1)

        # ===== Roof, Wall, Ground Materials Code =====
        layout.addWidget(self._bold_label("Roof and Ground Material Codes"))

        self.roof_color_input = QLineEdit("Color_A01")  # Default value
        self.ground_color_input = QLineEdit("Color_G01")  # Default value

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Roof:"))
        row2.addWidget(self.roof_color_input)
        row2.addWidget(QLabel("Ground:"))
        row2.addWidget(self.ground_color_input)

        layout.addLayout(row2)

        # ===== Output Directory and File Name =====
        layout.addWidget(self._bold_label("Output File"))
        self.output_path = QLineEdit()
        self.btn_browse_output = QPushButton("Browse")
        row3 = QHBoxLayout()
        row3.addWidget(self.output_path)
        row3.addWidget(self.btn_browse_output)
        layout.addLayout(row3)

        # ===== Process Button =====
        self.btn_process = QPushButton("Process")
        self.btn_process.setFont(QFont("Arial", 10, QFont.Bold))
        self.btn_process.setStyleSheet("padding: 8px;")
        layout.addWidget(self.btn_process)

        # ===== Log Output =====
        layout.addWidget(self._bold_label("Log Output"))
        self.log_window = QPlainTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(self.log_window)

        self.setLayout(layout)

        # Connect browse buttons
        self.btn_browse_obj.clicked.connect(self.browse_obj)
        self.btn_browse_output.clicked.connect(self.browse_output)
        self.btn_process.clicked.connect(self.process_files)

    def browse_obj(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OBJ File", "", "OBJ files (*.obj)")
        if path:
            self.input_obj.setText(path)

    def browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CityJSON File", "", "CityJSON files (*.json)")
        if path:
            self.output_path.setText(path)

    def process_files(self):
        self.log_window.clear()
        obj_path = self.input_obj.text().strip()
        output_path = self.output_path.text().strip()

        roof_color = self.roof_color_input.text().strip()  # Get roof color from user input
        ground_color = self.ground_color_input.text().strip()  # Get ground color from user input

        if not all([obj_path, output_path, roof_color, ground_color]):
            QMessageBox.warning(self, "Missing Input", "Please select all inputs and color codes.")
            return

        # Make sure the output file ends with .json
        out_path = self.output_path.text().strip()
        if not out_path.endswith(".json"):
            out_path += ".json"

        # Call the function to convert OBJ to CityJSON
        obj_to_cityjson_multiple_buildings(obj_path, out_path, roof_color, ground_color)

        self.log_window.appendPlainText(f"CityJSON file saved to: {out_path}")
        QMessageBox.information(self, "Process Complete", "The OBJ file has been processed successfully.")