from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QSizePolicy
)
from PyQt5.QtCore import Qt
import os
import subprocess

class MergeCityJSON(QWidget):
    def __init__(self):
        super().__init__()

        self.setMinimumSize(800, 400)
        layout = QVBoxLayout()

        # ===== Input CityJSON File 1 =====
        layout.addWidget(self._bold_label("Load CityJSON File 1"))
        self.cityjson_file1 = QLineEdit()
        btn_browse1 = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.cityjson_file1)
        row1.addWidget(btn_browse1)
        layout.addLayout(row1)

        # ===== Input CityJSON File 2 =====
        layout.addWidget(self._bold_label("Load CityJSON File 2"))
        self.cityjson_file2 = QLineEdit()
        btn_browse2 = QPushButton("Browse")
        row2 = QHBoxLayout()
        row2.addWidget(self.cityjson_file2)
        row2.addWidget(btn_browse2)
        layout.addLayout(row2)

        # ===== Output File Path (incl. filename) =====
        layout.addWidget(self._bold_label("Output File (e.g., output.json)"))
        self.output_file = QLineEdit()
        btn_browse_output = QPushButton("Save As")
        row3 = QHBoxLayout()
        row3.addWidget(self.output_file)
        row3.addWidget(btn_browse_output)
        layout.addLayout(row3)

        # ===== Merge Button =====
        self.btn_merge = QPushButton("Merge CityJSON")
        self.btn_merge.setStyleSheet("font-weight: bold; font-size: 16px; padding: 8px;")
        layout.addWidget(self.btn_merge)

        # ===== Log Console =====
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console)

        self.setLayout(layout)

        # Connections
        btn_browse1.clicked.connect(self.browse_file1)
        btn_browse2.clicked.connect(self.browse_file2)
        btn_browse_output.clicked.connect(self.browse_output)
        self.btn_merge.clicked.connect(self.merge_cityjson_files)

    def _bold_label(self, text):
        label = QLabel(f"<b>{text}</b>")
        return label

    def browse_file1(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select CityJSON File 1", "", "CityJSON Files (*.json)")
        if file_name:
            self.cityjson_file1.setText(file_name)
            self.log_console.append(f"📁 File 1 selected: {file_name}")

    def browse_file2(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select CityJSON File 2", "", "CityJSON Files (*.json)")
        if file_name:
            self.cityjson_file2.setText(file_name)
            self.log_console.append(f"📁 File 2 selected: {file_name}")

    def browse_output(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Output File", "", "CityJSON Files (*.json)")
        if file_name:
            self.output_file.setText(file_name)
            self.log_console.append(f"📄 Output file selected: {file_name}")

    def merge_cityjson_files(self):
        file1 = self.cityjson_file1.text()
        file2 = self.cityjson_file2.text()
        output = self.output_file.text()

        if not os.path.exists(file1) or not os.path.exists(file2):
            self.log_console.append("❌ One or both input files are invalid.")
            return
        if not output:
            self.log_console.append("❌ Output file path not specified.")
            return

        cmd = ["cjio", file1, "merge", file2, "save", output]
        self.log_console.append(f"🛠️ Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.log_console.append(result.stdout)
            if result.returncode != 0:
                self.log_console.append(f"❌ Error:\n{result.stderr}")
            else:
                self.log_console.append("✅ CityJSON files merged successfully.")
        except Exception as e:
            self.log_console.append(f"❌ Exception occurred:\n{e}")