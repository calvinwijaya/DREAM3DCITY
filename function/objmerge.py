import os
import time
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QTextEdit, 
    QFileDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QSizePolicy, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class MergeObjWorker(QThread):
    """Background worker to read, parse, offset, and merge OBJ files without freezing the UI."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, float)

    def __init__(self, path1, path2, output_path):
        super().__init__()
        self.path1 = path1
        self.path2 = path2
        self.output_path = output_path

    def run(self):
        start_time = time.perf_counter()
        try:
            self.log_signal.emit(f"📄 Reading {os.path.basename(self.path1)} into memory...")
            with open(self.path1, "r") as f1:
                lines1 = f1.readlines()

            self.log_signal.emit(f"📄 Reading {os.path.basename(self.path2)} into memory...")
            with open(self.path2, "r") as f2:
                lines2 = f2.readlines()

            vertices = []
            faces = []
            
            self.log_signal.emit("🔄 Parsing and merging vertices/faces...")

            # Read OBJ 1
            for line in lines1:
                if line.startswith("v "):
                    vertices.append(line)
                elif line.startswith("f "):
                    faces.append(line)

            vertex_offset = len(vertices)

            # Read OBJ 2 and adjust face indices
            for line in lines2:
                if line.startswith("v "):
                    vertices.append(line)
                elif line.startswith("f "):
                    parts = line.strip().split()
                    new_face = "f " + " ".join(
                        str(int(p.split("/")[0]) + vertex_offset) for p in parts[1:]
                    )
                    faces.append(new_face + "\n")

            self.log_signal.emit("💾 Writing merged OBJ to disk...")
            with open(self.output_path, "w") as fout:
                fout.writelines(vertices)
                fout.writelines(faces)

            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(True, f"Successfully merged to {os.path.basename(self.output_path)}", elapsed)

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(False, str(e), elapsed)


class OBJMerger(QWidget):
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
        input_group = QGroupBox("1. Input OBJs")
        input_layout = QVBoxLayout()
        
        # Input OBJ 1
        input_layout.addWidget(self._bold_label("Input OBJ 1"))
        row1 = QHBoxLayout()
        self.obj1_path = QLineEdit()
        self.obj1_path.setPlaceholderText("Select the first OBJ file...")
        btn1 = self._create_btn("Browse")
        btn1.clicked.connect(self.browse_obj1)
        row1.addWidget(self.obj1_path)
        row1.addWidget(btn1)
        input_layout.addLayout(row1)

        input_layout.addSpacing(5)

        # Input OBJ 2
        input_layout.addWidget(self._bold_label("Input OBJ 2"))
        row2 = QHBoxLayout()
        self.obj2_path = QLineEdit()
        self.obj2_path.setPlaceholderText("Select the second OBJ file to merge...")
        btn2 = self._create_btn("Browse")
        btn2.clicked.connect(self.browse_obj2)
        row2.addWidget(self.obj2_path)
        row2.addWidget(btn2)
        input_layout.addLayout(row2)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 2. Output Group
        output_group = QGroupBox("2. Output & Processing")
        output_layout = QVBoxLayout()
        
        output_layout.addWidget(self._bold_label("Select Output Directory and Filename"))
        row3 = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Define the merged OBJ filename...")
        btn3 = self._create_btn("Save As")
        btn3.clicked.connect(self.browse_output)
        row3.addWidget(self.output_path)
        row3.addWidget(btn3)
        output_layout.addLayout(row3)

        output_layout.addSpacing(10)

        # Merge Button
        self.merge_btn = self._create_btn("Merge OBJs", primary=True)
        self.merge_btn.clicked.connect(self.start_merge)
        output_layout.addWidget(self.merge_btn)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #E2E8F0; border: none; } QProgressBar::chunk { background-color: #2563EB; }")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 3. Log Console
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

    def browse_obj1(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OBJ 1", "", "OBJ Files (*.obj)")
        if path:
            self.obj1_path.setText(path)
            self.log(f"📁 OBJ 1 selected: {path}")

    def browse_obj2(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OBJ 2", "", "OBJ Files (*.obj)")
        if path:
            self.obj2_path.setText(path)
            self.log(f"📁 OBJ 2 selected: {path}")

    def browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Output OBJ File", "", "OBJ Files (*.obj)")
        if path:
            if not path.lower().endswith(".obj"):
                path += ".obj"
            self.output_path.setText(path)
            self.log(f"📁 Output file set to: {path}")

    def start_merge(self):
        path1 = self.obj1_path.text().strip()
        path2 = self.obj2_path.text().strip()
        output_path = self.output_path.text().strip()

        if not path1 or not os.path.exists(path1):
            QMessageBox.warning(self, "Missing Input", "Please select a valid file for OBJ 1.")
            return
        if not path2 or not os.path.exists(path2):
            QMessageBox.warning(self, "Missing Input", "Please select a valid file for OBJ 2.")
            return
        if not output_path:
            QMessageBox.warning(self, "Missing Output", "Please define an output path.")
            return

        # UI State Updates
        self.merge_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log("\n🚀 Starting OBJ merge process...")

        # Start Translation Worker
        self.worker = MergeObjWorker(path1, path2, output_path)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_merge_finished)
        self.worker.start()

    def on_merge_finished(self, success, message, elapsed):
        self.merge_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            finish_msg = f"✅ {message} in {elapsed:.2f} seconds."
            self.log(finish_msg)
            QMessageBox.information(self, "Process Complete", finish_msg)
        else:
            self.log(f"❌ Process failed:\n{message}")
            QMessageBox.critical(self, "Process Failed", f"An error occurred during merge:\n{message}")