import sys
import os
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel,
    QFileDialog, QLineEdit, QHBoxLayout, QMessageBox, QPlainTextEdit, QSizePolicy, QComboBox
)
from PyQt5.QtGui import QFont
import geopandas as gpd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt


def transform_obj_coordinates(input_obj, output_obj, local_reference, utm_reference):
    translation_vector = np.array(utm_reference) - np.array(local_reference)
    with open(input_obj, 'r') as infile, open(output_obj, 'w') as outfile:
        for line in infile:
            if line.startswith('v '):
                parts = line.split()
                x_local, y_local, z_local = map(float, parts[1:4])
                x_utm = x_local + translation_vector[0]
                y_utm = -z_local + translation_vector[2]
                z_utm = y_local + translation_vector[1]
                outfile.write(f"v {x_utm} {y_utm} {z_utm}\n")
            else:
                outfile.write(line)

class OBJTranslatorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBJ Translator based on GeoJSON Vertex")
        self.obj_file = ""
        self.geojson_file = ""
        self.utm_reference = None
        self.coordinates = []
        self.selected_marker = None
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

        # ===== Reference Input Method =====
        layout.addWidget(self._bold_label("Choose Reference Input Method"))
        self.reference_method = QComboBox()
        self.reference_method.addItems(["Write XY Coordinates Manually", "Interactive Select Vertex from GeoJSON"])
        layout.addWidget(self.reference_method)
        self.reference_method.currentIndexChanged.connect(self.toggle_reference_input_method)

        # ===== Manual Coordinate Input (Initially Hidden) =====
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

        # ===== Input GeoJSON File =====
        layout.addWidget(self._bold_label("Input GeoJSON File"))

        self.geojson_input_widget = QWidget()
        geojson_layout = QHBoxLayout()
        geojson_layout.setContentsMargins(0, 0, 0, 0)

        self.geojson_path = QLineEdit()
        self.btn_browse_geojson = QPushButton("Browse")
        geojson_layout.addWidget(self.geojson_path)
        geojson_layout.addWidget(self.btn_browse_geojson)

        self.geojson_input_widget.setLayout(geojson_layout)
        layout.addWidget(self.geojson_input_widget)

        # ===== GeoJSON Plot =====
        layout.addWidget(self._bold_label("GeoJSON Geometry (Click to Select Reference Vertex)"))

        self.canvas_container = QWidget()
        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.figure, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.setMinimumHeight(500)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas_layout.addWidget(self.canvas)
        self.canvas_container.setLayout(canvas_layout)
        layout.addWidget(self.canvas_container)

        # ===== Output File =====
        layout.addWidget(self._bold_label("Output OBJ File"))
        self.output_path = QLineEdit()
        self.btn_browse_output = QPushButton("Browse")
        row3 = QHBoxLayout()
        row3.addWidget(self.output_path)
        row3.addWidget(self.btn_browse_output)
        layout.addLayout(row3)

        # ===== Process Button =====
        self.btn_translate = QPushButton("Translate OBJ")
        self.btn_translate.setFont(QFont("Arial", 11, QFont.Bold))
        self.btn_translate.setStyleSheet("padding: 10px;")
        layout.addWidget(self.btn_translate)

        # ===== Log Output =====
        layout.addWidget(self._bold_label("Log Output"))
        self.log_window = QPlainTextEdit()
        self.log_window.setReadOnly(True)
        layout.addWidget(self.log_window)

        self.setLayout(layout)

        # Connect signals
        self.btn_browse_obj.clicked.connect(self.load_obj)
        self.btn_browse_geojson.clicked.connect(self.load_geojson)
        self.btn_browse_output.clicked.connect(self.select_output_file)
        self.btn_translate.clicked.connect(self.translate_obj)

        self.toggle_reference_input_method(self.reference_method.currentIndex())
        self.enable_panning()

    def log(self, message):
        self.log_window.appendPlainText(message)
        self.log_window.verticalScrollBar().setValue(self.log_window.verticalScrollBar().maximum())

    def toggle_reference_input_method(self, index):
        if index == 0:  # Manual input
            self.manual_coord_widget.show()
            self.canvas_container.hide()
            self.geojson_input_widget.setDisabled(True)
        else:  # Interactive
            self.manual_coord_widget.hide()
            self.canvas_container.show()
            self.geojson_input_widget.setDisabled(False)

    def load_obj(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select OBJ file", "", "OBJ Files (*.obj)")
        if file:
            self.obj_file = file
            self.obj_path.setText(file)
            self.log(f"Loaded OBJ file: {file}")

    def load_geojson(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select GeoJSON file", "", "GeoJSON Files (*.geojson *.json)")
        if file:
            self.geojson_file = file
            self.geojson_path.setText(file)
            self.log(f"Loaded GeoJSON file: {file}")
            self.display_geojson()

    def display_geojson(self):
        self.ax.clear()
        gdf = gpd.read_file(self.geojson_file)
        gdf.plot(ax=self.ax, edgecolor='black', facecolor='none')
        self.coordinates.clear()

        for geom in gdf.geometry:
            if geom.geom_type == 'Polygon':
                for x, y in geom.exterior.coords:
                    self.ax.plot(x, y, 'ro')
                    self.coordinates.append((x, y))
            elif geom.geom_type == 'MultiPolygon':
                for poly in geom.geoms:
                    for x, y in poly.exterior.coords:
                        self.ax.plot(x, y, 'ro')
                        self.coordinates.append((x, y))

        self.figure.tight_layout() 
        self.setFixedSize(self.size()) 
        self.setMinimumSize(1000, 750)
        self.canvas.draw()
        self.canvas.mpl_connect("button_press_event", self.select_vertex)
        self.log(f"Plotted {len(self.coordinates)} vertices.")

    def select_vertex(self, event):
        if event.xdata is None or event.ydata is None:
            return
        x_clicked, y_clicked = event.xdata, event.ydata
        closest = min(self.coordinates, key=lambda p: (p[0] - x_clicked) ** 2 + (p[1] - y_clicked) ** 2)
        self.utm_reference = [closest[0], closest[1], 0.0]

        if self.selected_marker:
            self.selected_marker.remove()
        self.selected_marker = self.ax.plot(closest[0], closest[1], 'go', markersize=10, label="Selected")[0]
        self.ax.legend()
        self.canvas.draw()

        self.log(f"Selected vertex: X={closest[0]:.2f}, Y={closest[1]:.2f}")

    def select_output_file(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Translated OBJ", "", "OBJ Files (*.obj)")
        if file:
            self.output_path.setText(file)
            self.log(f"Selected output file: {file}")

    def translate_obj(self):
        if not self.obj_path.text() or not self.output_path.text():
            QMessageBox.warning(self, "Incomplete Input", "Please select OBJ and Output path.")
            self.log("ERROR: Missing required input.")
            return

        # Handle UTM Reference based on input method
        if self.reference_method.currentIndex() == 0:  # Manual input
            try:
                x = float(self.input_x.text())
                y = float(self.input_y.text())
                self.utm_reference = [x, y, 0.0]
                self.log(f"Manual coordinates used: X={x}, Y={y}")
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric coordinates.")
                self.log("ERROR: Invalid manual coordinates.")
                return
        elif self.utm_reference is None:
            QMessageBox.warning(self, "No Vertex Selected", "Please select a vertex from the GeoJSON map.")
            self.log("ERROR: No vertex selected.")
            return
        
        try:
            transform_obj_coordinates(
                self.obj_path.text(),
                self.output_path.text(),
                local_reference=[0.0, 0.0, 0.0],  # Assume local OBJ coordinates origin
                utm_reference=self.utm_reference
            )
            self.log("Translation complete.")
        except Exception as e:
            self.log(f"ERROR: Translation failed. {str(e)}")
            QMessageBox.critical(self, "Translation Error", str(e))

    def on_scroll(self, event):
        base_scale = 1.2
        ax = self.ax
        xdata = event.xdata
        ydata = event.ydata

        if xdata is None or ydata is None:
            return

        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()

        x_left = xdata - cur_xlim[0]
        x_right = cur_xlim[1] - xdata
        y_bottom = ydata - cur_ylim[0]
        y_top = cur_ylim[1] - ydata

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
            self._press_event = event  # Update position

    def on_mouse_release(self, event):
        if event.button == 2:
            self._press_event = None

