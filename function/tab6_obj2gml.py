import os
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, 
    QFileDialog, QTextEdit, QSizePolicy, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt

from function.obj2gml.v2.main import RunObj2GML


class Obj2GML(QWidget):
    def __init__(self):
        super().__init__()
        self.start_time = 0.0

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # ===== Input Directory =====
        layout.addWidget(self._bold_label("Input Directory"))
        self.input_dir = QLineEdit()
        self.input_dir.setPlaceholderText("Select the directory containing OBJ files...")
        self.btn_browse_dir = QPushButton("Browse")
        
        row1 = QHBoxLayout()
        row1.addWidget(self.input_dir)
        row1.addWidget(self.btn_browse_dir)
        layout.addLayout(row1)

        # ===== Process Button & Progress Bar =====
        self.btn_process = QPushButton("Process to GML")
        self.btn_process.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 15px;
                padding: 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #94A3B8; color: #F1F5F9; }
        """)
        self.btn_process.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.btn_process)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #E2E8F0; border: none; border-radius: 3px; }
            QProgressBar::chunk { background-color: #2563EB; border-radius: 3px; }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ===== Log Console =====
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
        self.log_console.setMinimumHeight(180)
        layout.addWidget(self.log_console)

        self.setLayout(layout)

        # Connect Signals
        self.btn_browse_dir.clicked.connect(self.browse_dir)
        self.btn_process.clicked.connect(self.start_process)
    
    def _bold_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155;")
        return label

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.input_dir.setText(folder)
            self.log_console.append(f"📁 Directory selected: {folder}")
    
    def start_process(self):
        input_path = self.input_dir.text().strip()
        
        if not input_path or not os.path.isdir(input_path):
            QMessageBox.warning(self, "Missing Input", "Please select a valid files directory!")
            return
        
        # UI State updates
        self.btn_process.setEnabled(False)
        self.btn_process.setText("Translating OBJ to GML...")
        self.progress_bar.setVisible(True)
        self.log_console.append(f"\n🚀 Starting OBJ to GML translation pipeline...")
        self.start_time = time.perf_counter()

        # Initialize external Converter
        self.converter = RunObj2GML(input_path)
        
        # Connect signals
        self.converter.progress.connect(self.log_console.append)
        self.converter.finished.connect(self.on_processing_finished)
        self.converter.start()

    def on_processing_finished(self):
        elapsed = time.perf_counter() - self.start_time
        
        # Reset UI
        self.btn_process.setEnabled(True)
        self.btn_process.setText("Process to GML")
        self.progress_bar.setVisible(False)
        
        # Clean up worker memory
        self.converter.deleteLater()
        
        finish_msg = f"✅ OBJ to GML Conversion completed in {elapsed:.2f} seconds."
        self.log_console.append(finish_msg)
        QMessageBox.information(self, "Process Complete", finish_msg)