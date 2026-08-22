import os
import time
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QSizePolicy, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class MergeWorker(QThread):
    """Background worker to prevent UI freezing during large CityJSON merges."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, float)

    def __init__(self, file1, file2, output):
        super().__init__()
        self.file1 = file1
        self.file2 = file2
        self.output = output

    def run(self):
        start_time = time.perf_counter()
        cmd = ["cjio", self.file1, "merge", self.file2, "save", self.output]
        
        self.log_signal.emit(f"🛠️ Executing: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            for line in process.stdout:
                self.log_signal.emit(line.rstrip())

            process.wait()
            elapsed = time.perf_counter() - start_time

            if process.returncode != 0:
                self.finished_signal.emit(False, "cjio command failed. Check logs.", elapsed)
            else:
                self.finished_signal.emit(True, "CityJSON files merged successfully.", elapsed)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(False, f"Exception occurred: {str(e)}", elapsed)


class MergeCityJSON(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # ===== Input CityJSON File 1 =====
        layout.addWidget(self._bold_label("Load CityJSON File 1"))
        self.cityjson_file1 = QLineEdit()
        self.cityjson_file1.setPlaceholderText("Select the first CityJSON file (*.json)...")
        btn_browse1 = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.cityjson_file1)
        row1.addWidget(btn_browse1)
        layout.addLayout(row1)

        # ===== Input CityJSON File 2 =====
        layout.addWidget(self._bold_label("Load CityJSON File 2"))
        self.cityjson_file2 = QLineEdit()
        self.cityjson_file2.setPlaceholderText("Select the second CityJSON file (*.json)...")
        btn_browse2 = QPushButton("Browse")
        row2 = QHBoxLayout()
        row2.addWidget(self.cityjson_file2)
        row2.addWidget(btn_browse2)
        layout.addLayout(row2)

        # ===== Output File Path =====
        layout.addWidget(self._bold_label("Output File"))
        self.output_file = QLineEdit()
        self.output_file.setPlaceholderText("Define the merged output filename...")
        btn_browse_output = QPushButton("Save As")
        row3 = QHBoxLayout()
        row3.addWidget(self.output_file)
        row3.addWidget(btn_browse_output)
        layout.addLayout(row3)

        # ===== Merge Button & Progress Bar =====
        self.btn_merge = QPushButton("Merge CityJSON")
        self.btn_merge.setStyleSheet("""
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
        self.btn_merge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.btn_merge)

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

        # Connections
        btn_browse1.clicked.connect(self.browse_file1)
        btn_browse2.clicked.connect(self.browse_file2)
        btn_browse_output.clicked.connect(self.browse_output)
        self.btn_merge.clicked.connect(self.start_merge)

    def _bold_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155;")
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
            self.log_console.append(f"📄 Output file target: {file_name}")

    def start_merge(self):
        file1 = self.cityjson_file1.text().strip()
        file2 = self.cityjson_file2.text().strip()
        output = self.output_file.text().strip()

        if not os.path.exists(file1) or not os.path.exists(file2):
            QMessageBox.warning(self, "Invalid Input", "One or both input files are missing or invalid.")
            return
        if not output:
            QMessageBox.warning(self, "Missing Output", "Please specify an output file path.")
            return

        # UI State updates
        self.btn_merge.setEnabled(False)
        self.btn_merge.setText("Merging Data...")
        self.progress_bar.setVisible(True)
        self.log_console.append(f"\n🚀 Starting merge process...")

        self.worker = MergeWorker(file1, file2, output)
        self.worker.log_signal.connect(self.log_console.append)
        self.worker.finished_signal.connect(self.on_merge_finished)
        self.worker.start()

    def on_merge_finished(self, success, message, elapsed_seconds):
        self.btn_merge.setEnabled(True)
        self.btn_merge.setText("Merge CityJSON")
        self.progress_bar.setVisible(False)

        if success:
            finish_msg = f"✅ {message} Completed in {elapsed_seconds:.2f} seconds."
            self.log_console.append(finish_msg)
            QMessageBox.information(self, "Process Complete", finish_msg)
        else:
            self.log_console.append(f"❌ Process failed after {elapsed_seconds:.2f} seconds:\n{message}")
            QMessageBox.critical(self, "Process Failed", f"Merge failed:\n{message}")