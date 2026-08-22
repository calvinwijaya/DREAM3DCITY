import os
import json
import time
import numpy as np
import geopandas as gpd
from shapely.geometry import shape, Point
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QLineEdit,
    QHBoxLayout, QMessageBox, QPlainTextEdit, QSizePolicy, QComboBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class UTMTranslatorWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, float)

    def __init__(self, obj_in, obj_out, geojson_path, local_ref, utm_ref):
        super().__init__()
        self.obj_in = obj_in
        self.obj_out = obj_out
        self.geojson_path = geojson_path
        self.local_ref = local_ref
        self.utm_ref = utm_ref

    def run(self):
        start_time = time.perf_counter()
        temp_path = self.obj_out + ".tmp"
        
        try:
            self.log_signal.emit("🔄 Shifting coordinates to UTM...")
            translation_vector = np.array(self.utm_ref) - np.array(self.local_ref)
            
            with open(self.obj_in, 'r') as infile, open(temp_path, 'w') as outfile:
                for line in infile:
                    if line.startswith('v '):
                        parts = line.split()
                        x, y, z = map(float, parts[1:4])
                        outfile.write(f"v {x + translation_vector[0]:.4f} {y + translation_vector[1]:.4f} {z + translation_vector[2]:.4f}\n")
                    else:
                        outfile.write(line)

            self.log_signal.emit("🔄 Computing centroids and matching GeoJSON features...")
            
            with open(self.geojson_path) as f:
                gj = json.load(f)
            gj_centroids = [(shape(feat['geometry']).centroid, str(feat['properties']['fid'])) for feat in gj['features']]

            with open(temp_path) as f:
                lines = f.readlines()

            groups, current_group, v_list = [], None, []
            for line in lines:
                if line.startswith('v '):
                    v_list.append(list(map(float, line.strip().split()[1:4])))
                elif line.startswith('g '):
                    if current_group: groups.append(current_group)
                    current_group = {'name': line.strip().split()[1], 'lines': [line], 'faces': []}
                elif line.startswith('f ') and current_group:
                    current_group['lines'].append(line)
                    current_group['faces'].append(line)
                elif current_group:
                    current_group['lines'].append(line)
            if current_group: groups.append(current_group)

            updated_lines = []
            for group in groups:
                face_vertices = []
                for f_line in group['faces']:
                    indices = [int(p.split('/')[0]) - 1 for p in f_line.strip().split()[1:]]
                    face_vertices.extend([v_list[idx] for idx in indices if 0 <= idx < len(v_list)])
                
                if face_vertices:
                    centroid = Point(np.array(face_vertices).mean(axis=0))
                    closest_fid = min(gj_centroids, key=lambda gc: centroid.distance(gc[0]))[1]
                    updated_lines.append(f"g {closest_fid}\n")
                else:
                    updated_lines.append(group['lines'][0])
                
                updated_lines.extend(group['lines'][1:])

            self.log_signal.emit("💾 Writing final OBJ file...")
            with open(self.obj_out, 'w') as f:
                for v in v_list: f.write(f"v {v[0]} {v[1]} {v[2]}\n")
                f.writelines(updated_lines)

            os.remove(temp_path)
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(True, "Translation completed successfully.", elapsed)

        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(False, str(e), elapsed)


class OBJ2UTMTranslatorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.obj_file = ""
        self.geojson_file = ""
        self.utm_reference = None
        self.coordinates = []
        self.selected_marker = None
        self.init_ui()

    def _bold_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155; margin-top: 5px;")
        return label

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        layout.addWidget(self._bold_label("Input Local OBJ File"))
        self.obj_path = QLineEdit()
        self.btn_browse_obj = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.obj_path)
        row1.addWidget(self.btn_browse_obj)
        layout.addLayout(row1)

        layout.addWidget(self._bold_label("Reference Input Method"))
        self.reference_method = QComboBox()
        self.reference_method.addItems(["Write XY Coordinates Manually", "Interactive Select Vertex from GeoJSON"])
        layout.addWidget(self.reference_method)
        self.reference_method.currentIndexChanged.connect(self.toggle_reference_input_method)

        self.manual_coord_widget = QWidget()
        coord_layout = QHBoxLayout(self.manual_coord_widget)
        coord_layout.setContentsMargins(0, 0, 0, 0)
        self.input_x = QLineEdit()
        self.input_y = QLineEdit()
        coord_layout.addWidget(QLabel("X:"))
        coord_layout.addWidget(self.input_x)
        coord_layout.addWidget(QLabel("Y:"))
        coord_layout.addWidget(self.input_y)
        layout.addWidget(self.manual_coord_widget)

        layout.addWidget(self._bold_label("Input Base GeoJSON (For mapping)"))
        self.geojson_input_widget = QWidget()
        gj_layout = QHBoxLayout(self.geojson_input_widget)
        gj_layout.setContentsMargins(0, 0, 0, 0)
        self.geojson_path = QLineEdit()
        self.btn_browse_geojson = QPushButton("Browse")
        gj_layout.addWidget(self.geojson_path)
        gj_layout.addWidget(self.btn_browse_geojson)
        layout.addWidget(self.geojson_input_widget)

        self.canvas_container = QWidget()
        canvas_layout = QVBoxLayout(self.canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.figure, self.ax = plt.subplots(facecolor="#F8FAFC")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.setMinimumHeight(350)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas_layout.addWidget(self.canvas)
        layout.addWidget(self.canvas_container)

        layout.addWidget(self._bold_label("Output UTM OBJ File"))
        self.output_path = QLineEdit()
        self.btn_browse_output = QPushButton("Save As")
        row3 = QHBoxLayout()
        row3.addWidget(self.output_path)
        row3.addWidget(self.btn_browse_output)
        layout.addLayout(row3)

        self.btn_translate = QPushButton("Translate to UTM")
        self.btn_translate.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; font-size: 14px; padding: 10px; border-radius: 6px;")
        layout.addWidget(self.btn_translate)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.log_window = QPlainTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setStyleSheet("background-color: #0F172A; color: #F8FAFC; font-family: monospace; font-size: 11px;")
        self.log_window.setFixedHeight(120)
        layout.addWidget(self.log_window)

        self.btn_browse_obj.clicked.connect(self.load_obj)
        self.btn_browse_geojson.clicked.connect(self.load_geojson)
        self.btn_browse_output.clicked.connect(self.select_output_file)
        self.btn_translate.clicked.connect(self.translate_obj)

        self.toggle_reference_input_method(self.reference_method.currentIndex())
        self.enable_panning()

    def log(self, message):
        self.log_window.appendPlainText(message)

    def toggle_reference_input_method(self, index):
        if index == 0:
            self.manual_coord_widget.show()
            self.canvas_container.hide()
            self.geojson_input_widget.setDisabled(True)
        else:
            self.manual_coord_widget.hide()
            self.canvas_container.show()
            self.geojson_input_widget.setDisabled(False)

    def load_obj(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select OBJ file", "", "OBJ Files (*.obj)")
        if file:
            self.obj_file = file
            self.obj_path.setText(file)

    def load_geojson(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select GeoJSON file", "", "GeoJSON Files (*.geojson *.json)")
        if file:
            self.geojson_file = file
            self.geojson_path.setText(file)
            self.display_geojson()

    def display_geojson(self):
        self.ax.clear()
        if not self.geojson_file: return
        gdf = gpd.read_file(self.geojson_file)
        gdf.plot(ax=self.ax, edgecolor='#334155', facecolor='none')
        self.coordinates.clear()
        
        for geom in gdf.geometry:
            pts = geom.exterior.coords if geom.geom_type == 'Polygon' else [pt for p in geom.geoms for pt in p.exterior.coords]
            for x, y in pts:
                self.ax.plot(x, y, 'ro', markersize=2)
                self.coordinates.append((x, y))

        self.figure.tight_layout()
        self.ax.axis('off')
        self.canvas.draw()
        self.canvas.mpl_connect("button_press_event", self.select_vertex)

    def select_vertex(self, event):
        if event.button != 1 or event.xdata is None or event.ydata is None or not self.coordinates: return
        x, y = event.xdata, event.ydata
        closest = min(self.coordinates, key=lambda p: (p[0]-x)**2 + (p[1]-y)**2)
        self.utm_reference = [closest[0], closest[1], 0.0]

        if self.selected_marker: self.selected_marker.remove()
        self.selected_marker = self.ax.plot(closest[0], closest[1], 'go', markersize=8)[0]
        self.canvas.draw()
        self.log(f"📍 Selected target vertex: X={closest[0]:.2f}, Y={closest[1]:.2f}")

    def on_scroll(self, event):
        if event.xdata is None or event.ydata is None: return
        sf = 1/1.2 if event.button == 'up' else 1.2
        ax, xl, yl = self.ax, self.ax.get_xlim(), self.ax.get_ylim()
        ax.set_xlim([event.xdata - (event.xdata-xl[0])*sf, event.xdata + (xl[1]-event.xdata)*sf])
        ax.set_ylim([event.ydata - (event.ydata-yl[0])*sf, event.ydata + (yl[1]-event.ydata)*sf])
        self.canvas.draw_idle()

    def enable_panning(self):
        self._press_event = None
        self.canvas.mpl_connect("button_press_event", lambda e: setattr(self, "_press_event", e) if e.button == 2 else None)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
        self.canvas.mpl_connect("button_release_event", lambda e: setattr(self, "_press_event", None) if e.button == 2 else None)

    def on_mouse_drag(self, event):
        if self._press_event and event.button == 2 and event.xdata and event.ydata:
            dx, dy = event.xdata - self._press_event.xdata, event.ydata - self._press_event.ydata
            xl, yl = self.ax.get_xlim(), self.ax.get_ylim()
            self.ax.set_xlim(xl[0]-dx, xl[1]-dx)
            self.ax.set_ylim(yl[0]-dy, yl[1]-dy)
            self.canvas.draw()
            self._press_event = event

    def select_output_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Translated OBJ", "", "OBJ Files (*.obj)")
        if file: self.output_path.setText(file)

    def translate_obj(self):
        if not self.obj_path.text() or not self.output_path.text():
            QMessageBox.warning(self, "Input Missing", "Please select input and output paths.")
            return

        if self.reference_method.currentIndex() == 0:
            try: self.utm_reference = [float(self.input_x.text()), float(self.input_y.text()), 0.0]
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Invalid manual coordinates.")
                return
        elif not self.utm_reference:
            QMessageBox.warning(self, "No Vertex", "Select a vertex from the map.")
            return

        self.btn_translate.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log("🚀 Starting translation background task...")

        self.worker = UTMTranslatorWorker(
            self.obj_path.text(), self.output_path.text(), self.geojson_path.text(),
            [0.0, 0.0, 0.0], self.utm_reference
        )
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_translation_finished)
        self.worker.start()

    def on_translation_finished(self, success, msg, elapsed):
        self.btn_translate.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            self.log(f"✅ {msg} in {elapsed:.2f}s")
            QMessageBox.information(self, "Success", "Translation complete!")
        else:
            self.log(f"❌ Failed: {msg}")
            QMessageBox.critical(self, "Error", msg)