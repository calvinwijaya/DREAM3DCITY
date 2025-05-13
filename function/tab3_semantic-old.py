import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog, QVBoxLayout,
    QSlider, QLineEdit, QMessageBox, QHBoxLayout, QPlainTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from function.semantic_helper import *

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

        # ===== Input OBJ =====
        layout.addWidget(self._bold_label("Input OBJ File"))
        self.input_obj = QLineEdit()
        self.btn_browse_obj = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.input_obj)
        row1.addWidget(self.btn_browse_obj)
        layout.addLayout(row1)

        # === Ground Angle Threshold ===
        row_ground = QHBoxLayout()
        layout.addWidget(self._bold_label("Ground Angle Threshold (degrees)"))
        self.slider_ground = QSlider(Qt.Horizontal)
        self.slider_ground.setRange(0, 360)
        self.slider_ground.setValue(30)
        self.label_ground = QLabel("30°")
        self.slider_ground.valueChanged.connect(lambda val: self.label_ground.setText(f"{val}°"))
        row_ground.addWidget(self.slider_ground)
        row_ground.addWidget(self.label_ground)
        layout.addLayout(row_ground)

        # === Wall Min Angle ===
        row_wall_min = QHBoxLayout()
        layout.addWidget(self._bold_label("Wall Min Angle (degrees)"))
        self.slider_wall_min = QSlider(Qt.Horizontal)
        self.slider_wall_min.setRange(0, 360)
        self.slider_wall_min.setValue(60)
        self.label_wall_min = QLabel("60°")
        self.slider_wall_min.valueChanged.connect(lambda val: self.label_wall_min.setText(f"{val}°"))
        row_wall_min.addWidget(self.slider_wall_min)
        row_wall_min.addWidget(self.label_wall_min)
        layout.addLayout(row_wall_min)

        # === Wall Max Angle ===
        row_wall_max = QHBoxLayout()
        layout.addWidget(self._bold_label("Wall Max Angle (degrees)"))
        self.slider_wall_max = QSlider(Qt.Horizontal)
        self.slider_wall_max.setRange(0, 360)
        self.slider_wall_max.setValue(120)
        self.label_wall_max = QLabel("120°")
        self.slider_wall_max.valueChanged.connect(lambda val: self.label_wall_max.setText(f"{val}°"))
        row_wall_max.addWidget(self.slider_wall_max)
        row_wall_max.addWidget(self.label_wall_max)
        layout.addLayout(row_wall_max)

        # === Outwardness Threshold ===
        row_outward = QHBoxLayout()
        layout.addWidget(self._bold_label("Outwardness Threshold (0.00 – 1.00)"))
        self.slider_outwardness = QSlider(Qt.Horizontal)
        self.slider_outwardness.setRange(0, 100)
        self.slider_outwardness.setValue(30)
        self.label_outward = QLabel("0.30")
        self.slider_outwardness.valueChanged.connect(
            lambda val: self.label_outward.setText(f"{val / 100:.2f}")
        )
        row_outward.addWidget(self.slider_outwardness)
        row_outward.addWidget(self.label_outward)
        layout.addLayout(row_outward)

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
        ground_thresh = self.slider_ground.value()
        wall_min = self.slider_wall_min.value()
        wall_max = self.slider_wall_max.value()
        out_thresh = self.slider_outwardness.value() / 100.0


        if not all([obj_path, output_path]):
            QMessageBox.warning(self, "Missing Input", "Please select all inputs.")
            return

        out_path = self.output_path.text().strip()
        if not out_path.endswith(".json"):
            out_path += ".json"

        try:
            self.log_window.appendPlainText("Processing started...")
            self.log_window.appendPlainText(f"Loaded OBJ file: {obj_path}")
            self.log_window.appendPlainText("Parsing OBJ...")
            
            vertices, building_faces = load_obj_with_groups(obj_path)
            self.log_window.appendPlainText("Computing up vector...")

            self.log_window.appendPlainText("Classifying and merging faces...")

            all_vertices = []
            all_cityobjects = {}
            vertex_map = {}
            global_index = 0

            def get_global_index(v):
                nonlocal global_index
                v_tuple = tuple(np.round(v, 6))
                if v_tuple not in vertex_map:
                    vertex_map[v_tuple] = global_index
                    all_vertices.append(v_tuple)
                    global_index += 1
                return vertex_map[v_tuple]

            for i, (bname, face_list) in enumerate(building_faces.items()):
                cluster_faces = [[(v_idx, 0) for v_idx in face] for face in face_list]
                normals = [compute_face_normal(vertices, face) for face in cluster_faces]
                classified_faces = classify_faces(vertices, normals, cluster_faces, ground_angle_threshold=ground_thresh, wall_min_angle=wall_min, wall_max_angle=wall_max, outwardness_threshold=out_thresh)
                
                surface_types = ['RoofSurface', 'WallSurface', 'GroundSurface']
                cj_faces = []
                semantics_values = []

                for idx, surface in enumerate(surface_types):
                    for face in classified_faces[surface]:
                        indices = [get_global_index(vertices[v_idx]) for v_idx, _ in face]
                        cj_faces.append([indices])
                        semantics_values.append(idx)

                all_cityobjects[f"building-{i+1}"] = {
                    "type": "Building",
                    "geometry": [{
                        "type": "Solid",
                        "lod": "2.2",
                        "boundaries": [cj_faces],
                        "semantics": {
                            "surfaces": [{"type": t} for t in surface_types],
                            "values": [semantics_values]
                        }
                    }]
                }

            all_vertices_np = np.array(all_vertices)
            min_vals = all_vertices_np.min(axis=0)
            scale = [0.001, 0.001, 0.001]
            translate = [0, 0, 0]
            int_vertices = np.round((all_vertices_np - min_vals) / scale).astype(int).tolist()

            cityjson_combined = {
                "type": "CityJSON",
                "version": "2.0",
                "transform": {
                    "scale": scale,
                    "translate": translate
                },
                "CityObjects": all_cityobjects,
                "vertices": int_vertices
            }

            out_path = output_path
            with open(out_path, "w") as f:
                json.dump(cityjson_combined, f, indent=2)
            self.log_window.appendPlainText(f"CityJSON saved to: {output_path}")
            QMessageBox.information(self, "Success", f"CityJSON saved to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Processing Error", str(e))