import os
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QPlainTextEdit,
    QLabel, QFileDialog, QMessageBox, QLineEdit, QHBoxLayout
)
from PyQt5.QtGui import QFont
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from collections import defaultdict
from pyproj import Transformer

class OBJ2WGSTranslatorGUI(QWidget):
    def _bold_label(self, text):
        label = QLabel(text)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        return label

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # ===== Input OBJ File =====
        layout.addWidget(self._bold_label("Input OBJ File"))
        self.obj_path = QLineEdit()
        self.load_obj_button = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.obj_path)
        row1.addWidget(self.load_obj_button)
        layout.addLayout(row1)
        self.load_obj_button.clicked.connect(self.load_obj)

        # ===== Reference WGS84 Coordinate =====
        layout.addWidget(self._bold_label("Insert WGS84 Coordinates (lat, lon)"))
        self.wgs_input = QLineEdit()
        self.wgs_input.setPlaceholderText("-6.0000000,106.0000000")
        layout.addWidget(self.wgs_input)

        # ===== Output File =====
        layout.addWidget(self._bold_label("Output OBJ File"))
        self.output_path = QLineEdit()
        self.set_output_button = QPushButton("Browse")
        row2 = QHBoxLayout()
        row2.addWidget(self.output_path)
        row2.addWidget(self.set_output_button)
        layout.addLayout(row2)
        self.set_output_button.clicked.connect(self.set_output_directory)

        # ===== Process Button =====
        self.translate_button = QPushButton("Translate OBJ")
        self.translate_button.setFont(QFont("Arial", 11, QFont.Bold))
        self.translate_button.setStyleSheet("padding: 10px;")
        layout.addWidget(self.translate_button)
        self.translate_button.clicked.connect(self.translate_obj)

         # ===== Log Output =====
        layout.addWidget(self._bold_label("Log Output"))
        self.log_window = QPlainTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(self.log_window)

        self.setLayout(layout)        

        self.obj_file_path = ""
        self.mtl_file_path = ""
        self.output_dir = ""
        self.output_file_name = ""
        self.vertices = []
        self.faces = []

    def log(self, message):
        self.log_window.appendPlainText(message)
        self.log_window.verticalScrollBar().setValue(self.log_window.verticalScrollBar().maximum())

    def load_obj(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select OBJ file", "", "OBJ Files (*.obj)")
        if not file_path:
            return

        if file_path:
            self.obj_file_path = file_path
            self.log(f"Loaded OBJ file: {file_path}")

        self.obj_file_path = file_path
        self.obj_path.setText(file_path)

        self.vertices.clear()
        self.faces.clear()
        self.mtl_file_path = ""

        with open(file_path, "r") as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.strip().split()
                    x, y, z = map(float, parts[1:])
                    self.vertices.append((x, y, z))
                elif line.startswith("f "):
                    indices = [int(part.split("/")[0]) - 1 for part in line.strip().split()[1:]]
                    self.faces.append(indices)
                elif line.startswith("mtllib"):
                    mtl_filename = line.strip().split()[1]
                    self.mtl_file_path = os.path.join(os.path.dirname(file_path), mtl_filename)

    def set_output_directory(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Translated OBJ As",
            "",
            "OBJ Files (*.obj)"
        )
        self.output_path.setText(file_path)
        if file_path:
            if not file_path.lower().endswith(".obj"):
                file_path += ".obj"
            self.output_dir = os.path.dirname(file_path)
            self.output_file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.log(f"Selected output file: {file_path}")

    def get_utm_reference(self, epsg=32748):
        try:
            lat_lon = self.wgs_input.text().strip()
            lat_str, lon_str = lat_lon.split(",")
            lat = float(lat_str)
            lon = float(lon_str)

            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            x_utm, y_utm = transformer.transform(lon, lat)
            return x_utm, y_utm
        except Exception as e:
            self.log_window.appendPlainText(f"[Error] Invalid WGS84 input: {e}")
            return None, None
            
    def translate_obj(self):
        if not self.vertices:
            QMessageBox.warning(self, "Missing OBJ.", "Please select OBJ.")
            self.log("ERROR: Missing required input.")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "Output directory not set.", "Please select output path.")
            self.log("ERROR: Missing required input.")
            return

        def find_connected_components(faces, num_vertices):
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

            for face in faces:
                for i in range(1, len(face)):
                    union(face[i - 1], face[i])

            components = defaultdict(list)
            for v in range(num_vertices):
                root = find(v)
                components[root].append(v)

            return list(components.values())
        
        coords = np.array(self.vertices)  # (N, 3)
        components = find_connected_components(self.faces, len(coords))

        # Find the global minimum Z across all components
        component_min_z = []
        for comp in components:
            min_z = coords[comp, 2].min()
            component_min_z.append(min_z)

        global_min_z = min(component_min_z)

        # Shift each component so its base aligns to global_min_z
        local_coords = coords.copy()
        for comp, min_z in zip(components, component_min_z):
            offset = min_z - global_min_z
            local_coords[comp, 2] -= offset

        # --- Step: Translate to local origin using UTM reference ---
        x_utm, y_utm = self.get_utm_reference()

        if x_utm is not None and y_utm is not None:
            local_coords[:, 0] -= x_utm
            local_coords[:, 1] -= y_utm
            self.log_window.appendPlainText(f"Translated to local origin (UTM): X={x_utm:.3f}, Y={y_utm:.3f}")
        else:
            self.log_window.appendPlainText("Skipped local origin translation (no valid WGS84 input).")
        
        # --- Step 4: Write to new OBJ file ---
        base_name = self.output_file_name or os.path.splitext(os.path.basename(self.obj_file_path))[0] + "_local"
        new_obj_path = os.path.join(self.output_dir, base_name + ".obj")
        new_mtl_name = base_name + ".mtl"

        with open(self.obj_file_path, 'r') as infile, open(new_obj_path, 'w') as outfile:
            vertex_index = 0
            mtl_written = False

            for line in infile:
                if line.startswith("mtllib"):
                    outfile.write(f"mtllib {new_mtl_name}\n")
                    mtl_written = True
                elif line.startswith("v "):
                    x, y, z = local_coords[vertex_index]
                    outfile.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                    vertex_index += 1
                else:
                    outfile.write(line)

        # --- Step 5: Copy MTL ---
        if self.mtl_file_path and os.path.exists(self.mtl_file_path):
            shutil.copy(self.mtl_file_path, os.path.join(self.output_dir, new_mtl_name))

        self.log_window.appendPlainText(f"Translated OBJ saved to: {new_obj_path}")
        QMessageBox.information(self, "Translation Complete", "OBJ translated to local coordinates and flattened.")