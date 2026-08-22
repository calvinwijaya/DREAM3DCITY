import os
import time
import shutil
import numpy as np
from collections import defaultdict
from pyproj import Transformer

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QLineEdit, QTextEdit,
    QGroupBox, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class LoadObjWorkerWGS(QThread):
    """Background worker to parse OBJ files without freezing the UI."""
    finished = pyqtSignal(bool, list, list, str, str)  # success, vertices, faces, mtl_path, message

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        vertices = []
        faces = []
        mtl_file_path = ""
        try:
            with open(self.file_path, "r") as f:
                for line in f:
                    if line.startswith("v "):
                        parts = line.strip().split()
                        vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                    elif line.startswith("f "):
                        indices = [int(part.split("/")[0]) - 1 for part in line.strip().split()[1:]]
                        faces.append(indices)
                    elif line.startswith("mtllib"):
                        mtl_filename = line.strip().split()[1]
                        mtl_file_path = os.path.join(os.path.dirname(self.file_path), mtl_filename)
            
            self.finished.emit(True, vertices, faces, mtl_file_path, f"Loaded {len(vertices)} vertices and {len(faces)} faces.")
        except Exception as e:
            self.finished.emit(False, [], [], "", str(e))


class TranslateWGSWorker(QThread):
    """Background worker to handle pyproj transforms, Union-Find logic, and saving."""
    finished = pyqtSignal(bool, str, float)
    log_signal = pyqtSignal(str)

    def __init__(self, obj_path, out_path, lat, lon, epsg, vertices, faces, mtl_path, new_mtl_path, new_mtl_name):
        super().__init__()
        self.obj_path = obj_path
        self.out_path = out_path
        self.lat = lat
        self.lon = lon
        self.epsg = epsg
        self.vertices = vertices
        self.faces = faces
        self.mtl_path = mtl_path
        self.new_mtl_path = new_mtl_path
        self.new_mtl_name = new_mtl_name

    def run(self):
        start_time = time.perf_counter()
        try:
            # 1. Transform WGS84 to UTM
            self.log_signal.emit(f"🔄 Converting WGS84 ({self.lat}, {self.lon}) to UTM EPSG:{self.epsg}...")
            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{self.epsg}", always_xy=True)
            x_utm, y_utm = transformer.transform(self.lon, self.lat)
            self.log_signal.emit(f"📍 Target UTM Origin computed: X={x_utm:.3f}, Y={y_utm:.3f}")

            # 2. Find Connected Components via Union-Find
            self.log_signal.emit("🔍 Analyzing building components for Z-flattening...")
            num_vertices = len(self.vertices)
            parent = list(range(num_vertices))

            def find(u):
                while parent[u] != u:
                    parent[u] = parent[parent[u]]
                    u = parent[u]
                return u

            def union(u, v):
                pu, pv = find(u), find(v)
                if pu != pv:
                    parent[pu] = pv

            for face in self.faces:
                for i in range(1, len(face)):
                    union(face[i - 1], face[i])

            components = defaultdict(list)
            for v in range(num_vertices):
                root = find(v)
                components[root].append(v)

            self.log_signal.emit(f"⚙️ Found {len(components)} disconnected components. Flattening bases...")

            # 3. Flatten Components (Shift Z coordinates)
            coords = np.array(self.vertices)
            component_min_z = [coords[comp, 2].min() for comp in components.values()]
            global_min_z = min(component_min_z)

            local_coords = coords.copy()
            for comp, min_z in zip(components.values(), component_min_z):
                offset = min_z - global_min_z
                local_coords[comp, 2] -= offset

            # 4. Translate X and Y to local space based on UTM reference
            self.log_signal.emit("📐 Translating X and Y coordinates...")
            local_coords[:, 0] -= x_utm
            local_coords[:, 1] -= y_utm

            # 5. Write to new OBJ file
            self.log_signal.emit("💾 Writing translated OBJ file to disk...")
            with open(self.obj_path, 'r') as infile, open(self.out_path, 'w') as outfile:
                vertex_index = 0
                for line in infile:
                    if line.startswith("mtllib"):
                        outfile.write(f"mtllib {self.new_mtl_name}\n")
                    elif line.startswith("v "):
                        x, y, z = local_coords[vertex_index]
                        outfile.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                        vertex_index += 1
                    else:
                        outfile.write(line)

            # 6. Copy MTL file
            if self.mtl_path and os.path.exists(self.mtl_path):
                shutil.copy(self.mtl_path, self.new_mtl_path)

            elapsed = time.perf_counter() - start_time
            self.finished.emit(True, f"Translated OBJ saved to:\n{self.out_path}", elapsed)

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished.emit(False, str(e), elapsed)


class OBJ2WGSTranslatorGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # State variables
        self.obj_file_path = ""
        self.mtl_file_path = ""
        self.output_dir = ""
        self.output_file_name = ""
        self.vertices = []
        self.faces = []

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
        
        input_layout.addWidget(self._bold_label("Input OBJ File"))
        self.obj_path = QLineEdit()
        self.obj_path.setPlaceholderText("Select the OBJ file to translate...")
        self.load_obj_button = self._create_btn("Browse")
        self.load_obj_button.clicked.connect(self.load_obj)
        
        row1 = QHBoxLayout()
        row1.addWidget(self.obj_path)
        row1.addWidget(self.load_obj_button)
        input_layout.addLayout(row1)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 2. Reference Group
        ref_group = QGroupBox("2. Coordinate Reference")
        ref_layout = QVBoxLayout()
        
        ref_layout.addWidget(self._bold_label("Insert WGS84 Coordinates (Latitude, Longitude)"))
        self.wgs_input = QLineEdit()
        self.wgs_input.setPlaceholderText("-6.0000000, 106.0000000")
        ref_layout.addWidget(self.wgs_input)

        ref_layout.addWidget(self._bold_label("Target UTM EPSG Code"))
        self.epsg_input = QLineEdit()
        self.epsg_input.setText("32748")  # Default to user's original hardcoded zone
        ref_layout.addWidget(self.epsg_input)
        
        ref_group.setLayout(ref_layout)
        layout.addWidget(ref_group)

        # 3. Output Group
        output_group = QGroupBox("3. Output Processing")
        output_layout = QVBoxLayout()
        
        output_layout.addWidget(self._bold_label("Output OBJ File Directory"))
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select where to save the translated OBJ...")
        self.set_output_button = self._create_btn("Save As")
        self.set_output_button.clicked.connect(self.set_output_directory)
        
        row2 = QHBoxLayout()
        row2.addWidget(self.output_path)
        row2.addWidget(self.set_output_button)
        output_layout.addLayout(row2)

        self.translate_button = self._create_btn("Translate OBJ", primary=True)
        self.translate_button.clicked.connect(self.start_translation)
        output_layout.addSpacing(10)
        output_layout.addWidget(self.translate_button)
        
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

        # Log Window
        layout.addWidget(self._bold_label("Execution Log"))
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A; color: #F8FAFC;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12px; border-radius: 6px; padding: 8px; border: 1px solid #334155;
            }
        """)
        layout.addWidget(self.log_window)

    def log(self, message):
        self.log_window.append(message)

    def load_obj(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select OBJ file", "", "OBJ Files (*.obj)")
        if not file_path: return

        self.obj_file_path = file_path
        self.obj_path.setText(file_path)
        
        self.load_obj_button.setEnabled(False)
        self.translate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log(f"📁 Reading OBJ file: {file_path}")

        self.vertices.clear()
        self.faces.clear()
        self.mtl_file_path = ""

        # Run loading in background
        self.load_worker = LoadObjWorkerWGS(file_path)
        self.load_worker.finished.connect(self.on_obj_loaded)
        self.load_worker.start()

    def on_obj_loaded(self, success, vertices, faces, mtl_path, message):
        self.load_obj_button.setEnabled(True)
        self.translate_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.vertices = vertices
            self.faces = faces
            self.mtl_file_path = mtl_path
            self.log(f"✅ {message}")
        else:
            self.log(f"❌ Error loading OBJ: {message}")
            QMessageBox.critical(self, "Load Error", f"Failed to load OBJ file:\n{message}")

    def set_output_directory(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Translated OBJ As", "", "OBJ Files (*.obj)")
        if file_path:
            if not file_path.lower().endswith(".obj"): file_path += ".obj"
            self.output_path.setText(file_path)
            self.output_dir = os.path.dirname(file_path)
            self.output_file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.log(f"📁 Output set to: {file_path}")

    def start_translation(self):
        if not self.vertices:
            QMessageBox.warning(self, "Missing OBJ", "Please load an OBJ file first.")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "Missing Output", "Please specify an output file location.")
            return
        
        lat_lon = self.wgs_input.text().strip()
        epsg_text = self.epsg_input.text().strip()
        
        if not lat_lon or "," not in lat_lon:
            QMessageBox.warning(self, "Invalid WGS84", "Please provide Latitude and Longitude separated by a comma.")
            return
        
        try:
            lat_str, lon_str = lat_lon.split(",")
            lat, lon = float(lat_str), float(lon_str)
            epsg = int(epsg_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Inputs", "Latitude, Longitude, and EPSG must be numeric.")
            return

        base_name = self.output_file_name or os.path.splitext(os.path.basename(self.obj_file_path))[0] + "_local"
        new_obj_path = os.path.join(self.output_dir, base_name + ".obj")
        new_mtl_name = base_name + ".mtl"
        new_mtl_path = os.path.join(self.output_dir, new_mtl_name)

        # UI State Updates
        self.translate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log("\n🚀 Starting translation pipeline...")

        # Start Translation Worker
        self.trans_worker = TranslateWGSWorker(
            self.obj_file_path, new_obj_path, lat, lon, epsg,
            self.vertices, self.faces, self.mtl_file_path, new_mtl_path, new_mtl_name
        )
        self.trans_worker.log_signal.connect(self.log)
        self.trans_worker.finished.connect(self.on_translation_finished)
        self.trans_worker.start()

    def on_translation_finished(self, success, message, elapsed):
        self.translate_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            finish_msg = f"✅ Translation completed successfully in {elapsed:.2f} seconds."
            self.log(finish_msg)
            QMessageBox.information(self, "Translation Complete", f"{finish_msg}\n\n{message}")
        else:
            self.log(f"❌ Translation failed:\n{message}")
            QMessageBox.critical(self, "Process Failed", f"An error occurred during translation:\n{message}")