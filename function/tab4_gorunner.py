import os
import sys
import subprocess
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout,
    QHBoxLayout, QFileDialog, QComboBox, QPlainTextEdit, QSizePolicy, QMessageBox,
    QGridLayout, QCheckBox
)
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from function.obj2cityjson.separator import split_obj_by_geojson
from function.obj2cityjson.color import coloring_obj
from function.obj2cityjson.tojson import obj_folder_to_cityjson
from function.obj2cityjson.mergeobj import merge_obj_mtl
from function.obj2cityjson.json2gml import json2gml
import shutil

COLORS = {
    "ground": (0.36, 0.25, 0.20),
    "wall": (1.00, 1.00, 1.00),
    "roof": (1.00, 0.00, 0.00)
}

class GoRunner(QWidget):
    def __init__(self):
        super().__init__()
        self.obj_file = None
        self.geojson_file = None
        self.coordinates = []
        self.selected_marker = None
        self.utm_reference = None
        self._press_event = None

        self.init_ui()

    def _bold_label(self, text):
        label = QLabel(text)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        return label

    def init_ui(self):
        layout = QVBoxLayout()

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
        coord_layout = QHBoxLayout()

        self.label_x = QLabel("X Coordinate")
        self.input_x = QLineEdit()
        self.label_y = QLabel("Y Coordinate")
        self.input_y = QLineEdit()

        coord_layout.addWidget(self.label_x)
        coord_layout.addWidget(self.input_x)
        coord_layout.addWidget(self.label_y)
        coord_layout.addWidget(self.input_y)

        self.manual_coord_widget.setLayout(coord_layout)
        self.manual_coord_widget.hide()
        layout.addWidget(self.manual_coord_widget)

         # ===== GeoJSON Plot =====
        self.canvas_container = QWidget()
        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = plt.figure()
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.setMinimumHeight(500)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas_layout.addWidget(self.canvas)
        self.canvas_container.setLayout(canvas_layout)
        layout.addWidget(self.canvas_container)
        self.canvas_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.resize(self.canvas_container.size())

        # Prefix and User
        grid = QGridLayout()

        # Row 0: labels
        grid.addWidget(QLabel("<b>Prefix</b>"), 0, 0)
        grid.addWidget(QLabel("<b>User</b>"), 0, 1)
        grid.addWidget(QLabel("<b>EPSG Code</b>"), 0, 2)

        # Row 1: input fields
        self.prefix = QLineEdit()
        self.user = QLineEdit()
        self.epsg = QLineEdit()
        self.prefix.setPlaceholderText("Optional")
        self.user.setPlaceholderText("Optional")
        grid.addWidget(self.prefix, 1, 0)
        grid.addWidget(self.user, 1, 1)
        grid.addWidget(self.epsg, 1, 2)
        layout.addLayout(grid)

        # Output Type Selection
        layout.addWidget(self._bold_label("Choose Output"))

        self.output_obj = QCheckBox("OBJ")
        self.output_cityjson = QCheckBox("CityJSON")
        self.output_citygml = QCheckBox("CityGML")

        # Logic: disable CityJSON if OBJ is unchecked
        self.output_obj.stateChanged.connect(self.sync_output_checkboxes)
        self.output_cityjson.setEnabled(False)

        row_output = QHBoxLayout()
        row_output.addWidget(self.output_obj)
        row_output.addWidget(self.output_cityjson)
        row_output.addWidget(self.output_citygml)
        layout.addLayout(row_output)

        # Process button
        self.btn_process = QPushButton("Process")
        self.btn_process.setStyleSheet("font-weight: bold; padding: 8px;")
        self.btn_process.setFont(QFont("Arial", 11, QFont.Bold))
        layout.addWidget(self.btn_process)
        
        # Log
        layout.addWidget(self._bold_label("Log Output"))
        self.log_window = QPlainTextEdit()
        self.log_window.setReadOnly(True)
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

    def display_geojson(self):
        self.ax.clear()
        if not self.geojson_file:
            self.log("❌ No BO file loaded.")
            return
        gdf = gpd.read_file(self.geojson_file)
        gdf.plot(ax=self.ax, edgecolor='black', facecolor='none')
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
        
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_xlabel('')
        self.ax.set_ylabel('')
        self.ax.axis("off")

        self.canvas.draw()
        self.canvas.mpl_connect("button_press_event", self.select_vertex)

    def select_vertex(self, event):
        if event.button != 1 or event.xdata is None or event.ydata is None:
            return
        x_clicked, y_clicked = event.xdata, event.ydata
        closest = min(self.coordinates, key=lambda p: (p[0] - x_clicked) ** 2 + (p[1] - y_clicked) ** 2)
        self.utm_reference = (closest[0], closest[1])

        if self.selected_marker:
            self.selected_marker.remove()
        self.selected_marker = self.ax.plot(closest[0], closest[1], 'go', markersize=10, label="Selected")[0]
        self.ax.legend()
        self.canvas.draw()

        self.log(f"Selected vertex: X={closest[0]:.2f}, Y={closest[1]:.2f}")

    def log(self, message):
        self.log_window.appendPlainText(message)
        self.log_window.verticalScrollBar().setValue(self.log_window.verticalScrollBar().maximum())

    def on_scroll(self, event):
        base_scale = 1.2
        ax = self.ax
        xdata = event.xdata
        ydata = event.ydata

        if xdata is None or ydata is None:
            return

        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()

        x_left = event.xdata - cur_xlim[0]
        x_right = cur_xlim[1] - event.xdata
        y_bottom = event.ydata - cur_ylim[0]
        y_top = cur_ylim[1] - event.ydata

        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            scale_factor = 1

        ax.set_xlim([xdata - x_left * scale_factor, xdata + x_right * scale_factor])
        ax.set_ylim([ydata - y_bottom * scale_factor, ydata + y_top * scale_factor])
        self.canvas.draw_idle()

    def enable_panning(self):
        self._press_event = None
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)

    def on_mouse_press(self, event):
        if event.button == 2:  # Middle mouse button
            self._press_event = event

    def on_mouse_drag(self, event):
        if self._press_event and event.button == 2 and event.xdata and event.ydata:
            dx = event.xdata - self._press_event.xdata
            dy = event.ydata - self._press_event.ydata

            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)

            self.canvas.draw()
            self._press_event = event  # Update drag anchor point

    def on_mouse_release(self, event):
        if event.button == 2:
            self._press_event = None

    def run_obj2gml(self):
        obj_path = self.obj_path.text().strip()
        geojson_path = self.geojson_path.text().strip()

        if not obj_path or not geojson_path:
            QMessageBox.warning(self, "Missing Input", "Please select both OBJ and BO files.")
            return

        if self.reference_method.currentIndex() == 0:
            try:
                tx = float(self.input_x.text())
                ty = float(self.input_y.text())
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "X and Y must be numeric.")
                return
        else:
            if not self.utm_reference:
                QMessageBox.warning(self, "No Vertex", "No vertex selected.")
                return
            tx, ty = self.utm_reference
        self.log(f"Using coordinates: X={tx}, Y={ty}")

        origin_utm = (
            tuple(map(float, [self.input_x.text(), self.input_y.text(), 0.001]))
            if self.reference_method.currentIndex() == 0
            else self.utm_reference + (0.001,)
        )
        prefix = self.prefix.text() or None
        user = self.user.text() or None

        epsg = int(self.epsg.text()) if self.epsg.text().isdigit() else 32748
        
        obj_name = os.path.basename(obj_path)
        obj_stem = os.path.splitext(obj_name)[0]

        geojson_name = os.path.basename(geojson_path)
        geojson_stem = os.path.splitext(geojson_name)[0]

        output = os.path.dirname(obj_path)
        output_geojson = os.path.join(output, f"{geojson_stem}_Processed.geojson")
        output_merge_obj = os.path.join(output, f"{obj_stem}_merge.obj")
        output_mtl = os.path.join(output, f"{obj_stem}_merge.mtl")
        output_path = os.path.join(output, f"{obj_stem}.json")
        output_dir_temp = os.path.join(output, "temptrash")
        outputtemp_obj_color = os.path.join(output, "temptrash_color")

        try:
            obj_checked = self.output_obj.isChecked()
            cityjson_checked = self.output_cityjson.isChecked()
            citygml_checked = self.output_citygml.isChecked()

            if not obj_checked and not cityjson_checked and not citygml_checked:
                QMessageBox.warning(self, "No Output Selected", "Please select at least one output format (OBJ, CityJSON, CityGML).")
                return

                # === Only OBJ selected ===
            if obj_checked and not cityjson_checked and not citygml_checked:
                self.log("Starting process...")
                self.log_window.appendPlainText("📄 Read OBJ")
                self.log_window.appendPlainText("🔧 Start splitting OBJ by GeoJSON")
                self.log_window.appendPlainText(f"➡️  split_obj_by_geojson({obj_path}, {geojson_path}, {output_dir_temp}, {origin_utm}, {prefix}, {user}, {output_geojson})")
                split_obj_by_geojson(obj_path, geojson_path, output_dir_temp, origin_utm, prefix, user, output_geojson)

                self.log_window.appendPlainText("🎨 Coloring Process")
                self.log_window.appendPlainText(f"➡️  coloring_obj({output_dir_temp}, {outputtemp_obj_color}, COLORS)")
                coloring_obj(output_dir_temp, outputtemp_obj_color, COLORS)

                self.log_window.appendPlainText("✅ Coloring done, merging OBJ")
                merge_obj_mtl(outputtemp_obj_color, output_merge_obj, output_mtl)
                self.log_window.appendPlainText(f"✅ OBJ Merge done, output saved to: {output_merge_obj}")

                if cityjson_checked:
                    self.log_window.appendPlainText("🏙️ Start converting to CityJSON")
                    obj_folder_to_cityjson(outputtemp_obj_color, output_path, epsg)
                    self.log_window.appendPlainText(f"✅ Convert to CityJSON done, output saved to: {output_path}")
            
             # === Only CityGML selected ===
            elif citygml_checked and not obj_checked and not cityjson_checked:
                self.log("Starting process...")
                subprocess.run(
                    ["python", "function/obj2gml/obj2gmlrunner.py", obj_path, geojson_path, str(tx), str(ty), prefix or "", user or "", str(epsg)],
                    check=True,
                    text=True
                )
                self.log("✅ Process completed.")

                # === Both OBJ and CityGML selected ===
            elif obj_checked and citygml_checked:
                self.log("Starting process...")
                self.log_window.appendPlainText("📄 Read OBJ")
                self.log_window.appendPlainText("🔧 Start splitting OBJ by GeoJSON")
                self.log_window.appendPlainText(f"➡️  split_obj_by_geojson({obj_path}, {geojson_path}, {output_dir_temp}, {origin_utm}, {prefix}, {user}, {output_geojson})")
                split_obj_by_geojson(obj_path, geojson_path, output_dir_temp, origin_utm, prefix, user, output_geojson)

                self.log_window.appendPlainText("🎨 Coloring Process")
                self.log_window.appendPlainText(f"➡️  coloring_obj({output_dir_temp}, {outputtemp_obj_color}, COLORS)")
                coloring_obj(output_dir_temp, outputtemp_obj_color, COLORS)

                self.log_window.appendPlainText("✅ Coloring done, merging OBJ")
                merge_obj_mtl(outputtemp_obj_color, output_merge_obj, output_mtl)
                self.log_window.appendPlainText(f"✅ OBJ Merge done, output saved to: {output_merge_obj}")

                if cityjson_checked:
                    self.log_window.appendPlainText("🏙️ Start converting to CityJSON")
                    obj_folder_to_cityjson(outputtemp_obj_color, output_path, epsg)
                    self.log_window.appendPlainText(f"✅ Convert to CityJSON done, output saved to: {output_path}")
                
                self.log("🔁 Start converting to CityGML")
                subprocess.run(
                    ["python", "function/obj2gml/obj2gmlrunner2.py", outputtemp_obj_color, output_geojson, prefix or "", user or "", str(epsg), obj_path],
                    check=True,
                    text=True
                )
                self.log("✅ Process completed.")

        except subprocess.CalledProcessError as e:
            self.log(f"❌ Error occurred: {e}")

        finally:
            if os.path.exists(output_dir_temp):
                shutil.rmtree(output_dir_temp)
            if os.path.exists(outputtemp_obj_color):
                shutil.rmtree(outputtemp_obj_color)