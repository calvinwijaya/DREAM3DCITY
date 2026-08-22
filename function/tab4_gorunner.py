import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QFileDialog, QComboBox, QTextEdit, QSizePolicy, QMessageBox,
    QGridLayout, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Your custom function imports
from function.obj2cityjson.separator import split_obj_by_geojson
from function.obj2cityjson.color import coloring_obj
from function.obj2cityjson.tojson import obj_folder_to_cityjson
from function.obj2cityjson.mergeobj import merge_obj_mtl
from function.obj2cityjson.json2gml import json2gml


COLORS = {
    "ground": (0.36, 0.25, 0.20),
    "wall": (1.00, 1.00, 1.00),
    "roof": (1.00, 0.00, 0.00)
}

class GoRunnerWorker(QThread):
    """Background worker to handle the heavy OBJ processing without freezing the UI."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, float)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        start_time = time.perf_counter()
        
        # Extract variables from config dictionary for cleaner code
        obj_path = self.config['obj_path']
        geojson_path = self.config['geojson_path']
        output_dir_temp = self.config['output_dir_temp']
        origin_utm = self.config['origin_utm']
        prefix = self.config['prefix']
        user = self.config['user']
        output_geojson = self.config['output_geojson']
        outputtemp_obj_color = self.config['outputtemp_obj_color']
        output_merge_obj = self.config['output_merge_obj']
        output_mtl = self.config['output_mtl']
        output_path = self.config['output_path']
        epsg = self.config['epsg']
        tx, ty = self.config['tx'], self.config['ty']
        
        obj_checked = self.config['obj_checked']
        cityjson_checked = self.config['cityjson_checked']
        citygml_checked = self.config['citygml_checked']

        try:
            # === Only OBJ (and optionally CityJSON) selected ===
            if obj_checked and not citygml_checked:
                self.log_signal.emit("📄 Reading OBJ...")
                self.log_signal.emit("🔧 Splitting OBJ by GeoJSON...")
                split_obj_by_geojson(obj_path, geojson_path, output_dir_temp, origin_utm, prefix, user, output_geojson)

                self.log_signal.emit("🎨 Applying Colors...")
                coloring_obj(output_dir_temp, outputtemp_obj_color, COLORS)

                self.log_signal.emit("✅ Coloring done, merging OBJ...")
                merge_obj_mtl(outputtemp_obj_color, output_merge_obj, output_mtl)
                self.log_signal.emit(f"✅ OBJ Merge done, output saved to: {output_merge_obj}")

                if cityjson_checked:
                    self.log_signal.emit("🏙️ Converting to CityJSON...")
                    obj_folder_to_cityjson(outputtemp_obj_color, output_path, epsg)
                    self.log_signal.emit(f"✅ Convert to CityJSON done, output saved to: {output_path}")

            # === Only CityGML selected ===
            elif citygml_checked and not obj_checked and not cityjson_checked:
                self.log_signal.emit("🔁 Running CityGML translation script...")
                cmd = ["python", "function/obj2gml/obj2gmlrunner.py", obj_path, geojson_path, str(tx), str(ty), prefix or "", user or "", str(epsg)]
                self._run_subprocess(cmd)

            # === Both OBJ and CityGML selected ===
            elif obj_checked and citygml_checked:
                self.log_signal.emit("📄 Reading OBJ...")
                self.log_signal.emit("🔧 Splitting OBJ by GeoJSON...")
                split_obj_by_geojson(obj_path, geojson_path, output_dir_temp, origin_utm, prefix, user, output_geojson)

                self.log_signal.emit("🎨 Applying Colors...")
                coloring_obj(output_dir_temp, outputtemp_obj_color, COLORS)

                self.log_signal.emit("✅ Coloring done, merging OBJ...")
                merge_obj_mtl(outputtemp_obj_color, output_merge_obj, output_mtl)
                self.log_signal.emit(f"✅ OBJ Merge done, output saved to: {output_merge_obj}")

                if cityjson_checked:
                    self.log_signal.emit("🏙️ Converting to CityJSON...")
                    obj_folder_to_cityjson(outputtemp_obj_color, output_path, epsg)
                    self.log_signal.emit(f"✅ Convert to CityJSON done, output saved to: {output_path}")
                
                self.log_signal.emit("🔁 Converting colored OBJ to CityGML...")
                cmd = ["python", "function/obj2gml/obj2gmlrunner2.py", outputtemp_obj_color, output_geojson, prefix or "", user or "", str(epsg), obj_path]
                self._run_subprocess(cmd)

            # Cleanup
            if os.path.exists(output_dir_temp):
                shutil.rmtree(output_dir_temp)
            if os.path.exists(outputtemp_obj_color):
                shutil.rmtree(outputtemp_obj_color)

            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(True, "Process completed successfully.", elapsed)

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(False, str(e), elapsed)

    def _run_subprocess(self, cmd):
        self.log_signal.emit(f"🛠️ Executing: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace"
        )
        for line in process.stdout:
            self.log_signal.emit(line.rstrip())
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)


class GoRunner(QWidget):
    def __init__(self):
        super().__init__()
        self.obj_file = None
        self.geojson_file = None
        self.coordinates = []
        self.selected_marker = None
        self.utm_reference = None
        self._press_event = None
        self.worker = None

        self.init_ui()

    def _bold_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155; margin-top: 5px;")
        return label

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ===== Input OBJ File =====
        layout.addWidget(self._bold_label("Input OBJ File"))
        self.obj_path = QLineEdit()
        self.btn_browse_obj = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.obj_path)
        row1.addWidget(self.btn_browse_obj)
        layout.addLayout(row1)

        # ===== Input GeoJSON File =====
        layout.addWidget(self._bold_label("Input BO GeoJSON File"))
        self.geojson_path = QLineEdit()
        self.btn_browse_geojson = QPushButton("Browse")
        row2 = QHBoxLayout()
        row2.addWidget(self.geojson_path)
        row2.addWidget(self.btn_browse_geojson)
        layout.addLayout(row2)

        # ===== Reference Input Method =====
        layout.addWidget(self._bold_label("Choose Reference Input Method"))
        self.reference_method = QComboBox()
        self.reference_method.addItems(["Write XY Coordinates Manually", "Interactive Select Vertex from GeoJSON"])
        self.reference_method.currentIndexChanged.connect(self.toggle_reference_input_method)
        layout.addWidget(self.reference_method)

        # ===== Manual Coordinate Input =====
        self.manual_coord_widget = QWidget()
        coord_layout = QHBoxLayout(self.manual_coord_widget)
        coord_layout.setContentsMargins(0, 0, 0, 0)

        self.label_x = QLabel("X:")
        self.input_x = QLineEdit()
        self.label_y = QLabel("Y:")
        self.input_y = QLineEdit()

        coord_layout.addWidget(self.label_x)
        coord_layout.addWidget(self.input_x)
        coord_layout.addWidget(self.label_y)
        coord_layout.addWidget(self.input_y)
        
        self.manual_coord_widget.hide()
        layout.addWidget(self.manual_coord_widget)

        # ===== GeoJSON Plot (Matplotlib) =====
        self.canvas_container = QWidget()
        canvas_layout = QVBoxLayout(self.canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.figure = plt.figure(facecolor='#F8FAFC')
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.setMinimumHeight(350)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        canvas_layout.addWidget(self.canvas)
        layout.addWidget(self.canvas_container)

        # ===== Prefix, User, EPSG Grid =====
        grid = QGridLayout()
        grid.addWidget(self._bold_label("Prefix (Optional)"), 0, 0)
        grid.addWidget(self._bold_label("User (Optional)"), 0, 1)
        grid.addWidget(self._bold_label("EPSG Code"), 0, 2)

        self.prefix = QLineEdit()
        self.user = QLineEdit()
        self.epsg = QLineEdit()
        self.epsg.setText("32748")  # Default Fallback
        
        grid.addWidget(self.prefix, 1, 0)
        grid.addWidget(self.user, 1, 1)
        grid.addWidget(self.epsg, 1, 2)
        layout.addLayout(grid)

        # ===== Output Type Selection =====
        layout.addWidget(self._bold_label("Choose Output formats"))
        
        self.output_obj = QCheckBox("OBJ")
        self.output_cityjson = QCheckBox("CityJSON")
        self.output_citygml = QCheckBox("CityGML")

        self.output_obj.stateChanged.connect(self.sync_output_checkboxes)
        self.output_cityjson.setEnabled(False)

        row_output = QHBoxLayout()
        row_output.addWidget(self.output_obj)
        row_output.addWidget(self.output_cityjson)
        row_output.addWidget(self.output_citygml)
        layout.addLayout(row_output)

        # ===== Process Button & Loading Bar =====
        self.btn_process = QPushButton("Process Data")
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
        layout.addWidget(self.btn_process)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #E2E8F0; border: none; } QProgressBar::chunk { background-color: #2563EB; }")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ===== Log Output =====
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
        self.log_window.setMinimumHeight(150)
        layout.addWidget(self.log_window)

        self.setLayout(layout)

        # Connect signals
        self.btn_browse_obj.clicked.connect(self.load_obj)
        self.btn_browse_geojson.clicked.connect(self.load_geojson)
        self.btn_process.clicked.connect(self.run_obj2gml)

        self.toggle_reference_input_method(self.reference_method.currentIndex())
        self.enable_panning()

    def sync_output_checkboxes(self):
        if not self.output_obj.isChecked():
            self.output_cityjson.setChecked(False)
            self.output_cityjson.setEnabled(False)
        else:
            self.output_cityjson.setEnabled(True)
    
    def toggle_reference_input_method(self, index):
        if index == 0:  # Manual input
            self.manual_coord_widget.show()
            self.canvas_container.hide()
        else:  # Interactive
            self.manual_coord_widget.hide()
            self.canvas_container.show()
            self.display_geojson()

    def load_obj(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select OBJ File", "", "OBJ files (*.obj)")
        if file:
            self.obj_file = file
            self.obj_path.setText(file)
            self.log(f"📂 Loaded OBJ file: {file}")

    def load_geojson(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select GeoJSON File", "", "GeoJSON files (*.geojson *.json)")
        if file:
            self.geojson_file = file
            self.geojson_path.setText(file)
            self.log(f"🌍 Loaded GeoJSON file: {file}")
            if self.reference_method.currentIndex() == 1:
                self.display_geojson()

    def display_geojson(self):
        self.ax.clear()
        if not self.geojson_file:
            return
        try:
            gdf = gpd.read_file(self.geojson_file)
            gdf.plot(ax=self.ax, edgecolor='#1E293B', facecolor='none')
            self.coordinates.clear()

            for geom in gdf.geometry:
                if geom.geom_type == 'Polygon':
                    for x, y in geom.exterior.coords:
                        self.ax.plot(x, y, 'ro', markersize=2)
                        self.coordinates.append((x, y))
                elif geom.geom_type == 'MultiPolygon':
                    for poly in geom.geoms:
                        for x, y in poly.exterior.coords:
                            self.ax.plot(x, y, 'ro', markersize=2)
                            self.coordinates.append((x, y))

            self.figure.tight_layout() 
            self.ax.axis("off")
            self.canvas.draw()
            self.canvas.mpl_connect("button_press_event", self.select_vertex)
        except Exception as e:
            self.log(f"❌ Failed to display GeoJSON: {str(e)}")

    def select_vertex(self, event):
        if event.button != 1 or event.xdata is None or event.ydata is None or not self.coordinates:
            return
        x_clicked, y_clicked = event.xdata, event.ydata
        closest = min(self.coordinates, key=lambda p: (p[0] - x_clicked) ** 2 + (p[1] - y_clicked) ** 2)
        self.utm_reference = (closest[0], closest[1])

        if self.selected_marker:
            self.selected_marker.remove()
        self.selected_marker = self.ax.plot(closest[0], closest[1], 'go', markersize=10, label="Selected")[0]
        self.canvas.draw()
        self.log(f"📍 Selected vertex: X={closest[0]:.2f}, Y={closest[1]:.2f}")

    def log(self, message):
        self.log_window.append(message)

    def on_scroll(self, event):
        base_scale = 1.2
        if event.xdata is None or event.ydata is None: return

        cur_xlim, cur_ylim = self.ax.get_xlim(), self.ax.get_ylim()
        x_left, x_right = event.xdata - cur_xlim[0], cur_xlim[1] - event.xdata
        y_bottom, y_top = event.ydata - cur_ylim[0], cur_ylim[1] - event.ydata

        scale_factor = 1 / base_scale if event.button == 'up' else base_scale if event.button == 'down' else 1
        self.ax.set_xlim([event.xdata - x_left * scale_factor, event.xdata + x_right * scale_factor])
        self.ax.set_ylim([event.ydata - y_bottom * scale_factor, event.ydata + y_top * scale_factor])
        self.canvas.draw_idle()

    def enable_panning(self):
        self._press_event = None
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)

    def on_mouse_press(self, event):
        if event.button == 2: self._press_event = event

    def on_mouse_drag(self, event):
        if self._press_event and event.button == 2 and event.xdata and event.ydata:
            dx, dy = event.xdata - self._press_event.xdata, event.ydata - self._press_event.ydata
            xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            self.canvas.draw()
            self._press_event = event

    def on_mouse_release(self, event):
        if event.button == 2: self._press_event = None

    def run_obj2gml(self):
        obj_path = self.obj_path.text().strip()
        geojson_path = self.geojson_path.text().strip()

        if not obj_path or not geojson_path:
            QMessageBox.warning(self, "Missing Input", "Please select both OBJ and BO files.")
            return

        tx, ty = 0.0, 0.0
        if self.reference_method.currentIndex() == 0:
            try:
                tx, ty = float(self.input_x.text()), float(self.input_y.text())
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Manual X and Y coordinates must be numeric.")
                return
        else:
            if not self.utm_reference:
                QMessageBox.warning(self, "No Vertex", "Please click a vertex on the GeoJSON plot first.")
                return
            tx, ty = self.utm_reference

        obj_checked = self.output_obj.isChecked()
        cityjson_checked = self.output_cityjson.isChecked()
        citygml_checked = self.output_citygml.isChecked()

        if not obj_checked and not cityjson_checked and not citygml_checked:
            QMessageBox.warning(self, "No Output Selected", "Please select at least one output format.")
            return

        origin_utm = (tx, ty, 0.001)
        prefix = self.prefix.text() or None
        user = self.user.text() or None
        epsg = int(self.epsg.text()) if self.epsg.text().isdigit() else 32748

        # Define output variables
        obj_name = os.path.basename(obj_path)
        obj_stem = os.path.splitext(obj_name)[0]
        geojson_name = os.path.basename(geojson_path)
        geojson_stem = os.path.splitext(geojson_name)[0]
        output = os.path.dirname(obj_path)

        # Build Config Dictionary to pass to worker
        config = {
            'obj_path': obj_path, 'geojson_path': geojson_path, 'tx': tx, 'ty': ty,
            'origin_utm': origin_utm, 'prefix': prefix, 'user': user, 'epsg': epsg,
            'output_dir_temp': os.path.join(output, "temptrash"),
            'outputtemp_obj_color': os.path.join(output, "temptrash_color"),
            'output_geojson': os.path.join(output, f"{geojson_stem}_Processed.geojson"),
            'output_merge_obj': os.path.join(output, f"{obj_stem}_merge.obj"),
            'output_mtl': os.path.join(output, f"{obj_stem}_merge.mtl"),
            'output_path': os.path.join(output, f"{obj_stem}.json"),
            'obj_checked': obj_checked, 'cityjson_checked': cityjson_checked, 'citygml_checked': citygml_checked
        }

        # UI Updates
        self.btn_process.setEnabled(False)
        self.btn_process.setText("Processing Data...")
        self.progress_bar.setVisible(True)
        self.log(f"\n🚀 Starting pipeline using coordinates: X={tx}, Y={ty}")

        # Start Thread
        self.worker = GoRunnerWorker(config)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_processing_finished)
        self.worker.start()

    def on_processing_finished(self, success, message, elapsed):
        self.btn_process.setEnabled(True)
        self.btn_process.setText("Process Data")
        self.progress_bar.setVisible(False)

        if success:
            finish_msg = f"✅ {message} Completed in {elapsed:.2f} seconds."
            self.log(finish_msg)
            QMessageBox.information(self, "Process Complete", finish_msg)
        else:
            self.log(f"❌ Process failed after {elapsed:.2f} seconds:\n{message}")
            QMessageBox.critical(self, "Process Failed", f"Pipeline failed:\n{message}")