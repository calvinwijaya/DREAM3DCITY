from PyQt5.QtWidgets import (
  QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QFileDialog, QTextEdit, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt

import time
from datetime import datetime
import os
import tqdm
import sys
from tqdm import tqdm
from pathlib import Path

from function.obj2gml.v2.main import RunObj2GML

class Obj2GML(QWidget):
    def __init__(self):
        super().__init__()
        # UI components
        layout = QVBoxLayout()

        # ===== Input Building Footprint =====
        layout.addWidget(self._bold_label("Input the files directory"))

        self.input_dir = QLineEdit()
        self.btn_browse_dir = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.input_dir)
        row1.addWidget(self.btn_browse_dir)
        layout.addLayout(row1)

        # ===== Process Button =====
        self.btn_process = QPushButton("Process")
        self.btn_process.setStyleSheet("font-weight: bold; font-size: 20px; padding: 10px;")
        self.btn_process.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Make button fill the width
        # Add button to a horizontal layout to make it stretch
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_process)
        button_layout.setStretch(0, 1)

        layout.addLayout(button_layout)
        # ===== Log Console =====
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console)

        self.setLayout(layout)

        # Converter
        self.converter = RunObj2GML(self.log_console)

        # Connect
        self.btn_browse_dir.clicked.connect(self.browse_dir)
        self.btn_process.clicked.connect(self.process)
    
    def process(self):
        if not self.input_dir.text():
            QMessageBox.warning(self, "Missing Input", "Please select the files directory!")
            return
        
        self.converter.process(self.input_dir.text())

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)
            self.log_console.append(f"📁 Point Cloud selected: {folder}")
    
    def _bold_label(self, text):
        label = QLabel(f"<b>{text}</b>")
        return label

    def log_with_timestamp(self, message):
        """Print message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")