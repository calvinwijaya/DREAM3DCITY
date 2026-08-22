import os
import time
import shutil
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QGroupBox, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.collections import LineCollection


class LoadObjWorker(QThread):
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
            
            self.finished.emit(True, vertices, faces, mtl_file_path, f"Loaded {len(vertices)} vertices.")
        except Exception as e:
            self.finished.emit(False, [], [], "", str(e))


class TranslateObjWorker(QThread):
    """Background worker to translate and save the new OBJ without freezing the UI."""
    finished = pyqtSignal(bool, str, float)  # success, message, elapsed_time

    def __init__(self, obj_path, new_obj_path, picked_point, mtl_path, new_mtl_path, new_mtl_name):
        super().__init__()
        self.obj_path = obj_path
        self.new_obj_path = new_obj_path
        self.picked_point = picked_point
        self.mtl_path = mtl_path
        self.new_mtl_path = new_mtl_path
        self.new_mtl_name = new_mtl_name

    def run(self):
        start_time = time.perf_counter()
        try:
            with open(self.obj_path, 'r') as infile, open(self.new_obj_path, 'w') as outfile:
                for line in infile:
                    if line.startswith("v "):
                        parts = line.strip().split()
                        x, y, z = map(float, parts[1:])
                        x -= self.picked_point[0]
                        y -= self.picked_point[1]
                        z -= self.picked_point[2]
                        outfile.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                    elif line.startswith("mtllib"):
                        outfile.write(f"mtllib {self.new_mtl_name}\n")
                    else:
                        outfile.write(line)

            if self.mtl_path and os.path.exists(self.mtl_path):
                shutil.copy(self.mtl_path, self.new_mtl_path)

            elapsed = time.perf_counter() - start_time
            self.finished.emit(True, f"Translated OBJ saved to:\n{self.new_obj_path}", elapsed)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished.emit(False, str(e), elapsed)


class OBJ2LocalTranslatorGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Data state
        self.obj_file_path = ""
        self.mtl_file_path = ""
        self.output_dir = ""
        self.output_file_name = ""
        self.vertices = []      # [(x, y, z)]
        self.faces = []         # [[v1, v2, v3, ...]]
        self.picked_point = None
        self._press_event = None

        self.setup_ui()

    def _bold_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #334155; margin-bottom: 4px;")
        return lbl

    def _create_btn(self, text, primary=False):
        btn = QPushButton(text)
        if primary:
            btn.setStyleSheet("""
                QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 10px; border-radius: 6px; border: none; }
                QPushButton:hover { background-color: #1D4ED8; }
                QPushButton:disabled { background-color: #94A3B8; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px; }
                QPushButton:hover { background-color: #F1F5F9; }
            """)
        return btn

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # === Left Panel ===
        left_panel_widget = QWidget()
        left_panel_widget.setFixedWidth(300)
        left_panel_widget.setStyleSheet("background-color: #F8FAFC; border-right: 1px solid #E2E8F0;")
        left_panel = QVBoxLayout(left_panel_widget)
        left_panel.setContentsMargins(15, 15, 15, 15)
        left_panel.setSpacing(15)

        # Input Group
        input_group = QGroupBox("1. Input Data")
        input_layout = QVBoxLayout()
        self.load_button = self._create_btn("Load OBJ File")
        self.load_button.clicked.connect(self.load_obj)
        input_layout.addWidget(self.load_button)
        input_group.setLayout(input_layout)
        left_panel.addWidget(input_group)

        # View Group
        view_group = QGroupBox("2. View Controls")
        view_layout = QVBoxLayout()
        self.reset_view_button = self._create_btn("Reset Map View")
        self.reset_view_button.clicked.connect(self.reset_view)
        view_layout.addWidget(self.reset_view_button)
        view_group.setLayout(view_layout)
        left_panel.addWidget(view_group)

        # Output & Translation Group
        output_group = QGroupBox("3. Output & Processing")
        output_layout = QVBoxLayout()
        self.set_output_button = self._create_btn("Set Output Directory")
        self.set_output_button.clicked.connect(self.set_output_directory)
        
        self.translate_button = self._create_btn("Translate to Local", primary=True)
        self.translate_button.clicked.connect(self.start_translation)
        
        output_layout.addWidget(self.set_output_button)
        output_layout.addSpacing(10)
        output_layout.addWidget(self.translate_button)
        output_group.setLayout(output_layout)
        left_panel.addWidget(output_group)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #E2E8F0; border: none; } QProgressBar::chunk { background-color: #2563EB; }")
        self.progress_bar.setVisible(False)
        left_panel.addWidget(self.progress_bar)

        # Status Label
        self.status_label = QLabel("No OBJ file loaded. Please load a file to begin.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #475569; font-size: 11px;")
        left_panel.addWidget(self.status_label)
        left_panel.addStretch()

        main_layout.addWidget(left_panel_widget)

        # === Right Side: Matplotlib Canvas ===
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = plt.figure(facecolor='#F8FAFC')
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        canvas_layout.addWidget(self.canvas)
        main_layout.addWidget(canvas_container)

        # Matplotlib Events
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.enable_panning()
        self._clear_canvas()

    def _clear_canvas(self):
        self.ax.clear()
        self.ax.axis("off")
        self.ax.set_navigate(True)
        self.canvas.draw()

    # ============================
    # Loading & Plotting
    # ============================
    def load_obj(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open OBJ", "", "OBJ Files (*.obj)")
        if not file_path: return

        self.load_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Reading OBJ file... this may take a moment.")

        self.obj_file_path = file_path
        self.vertices.clear()
        self.faces.clear()
        self.mtl_file_path = ""
        self.picked_point = None

        self.worker = LoadObjWorker(file_path)
        self.worker.finished.connect(self.on_obj_loaded)
        self.worker.start()

    def on_obj_loaded(self, success, vertices, faces, mtl_path, message):
        self.load_button.setEnabled(True)
        
        if not success:
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"❌ Failed to load OBJ: {message}")
            return

        self.vertices = vertices
        self.faces = faces
        self.mtl_file_path = mtl_path
        self.status_label.setText(f"✅ {message} Plotting map...")

        self.plot_obj()
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"✅ {message} Click a vertex to set the local origin.")

    def plot_obj(self):
        self._clear_canvas()
        if not self.vertices: return

        coords = np.array(self.vertices)
        
        # High-performance plotting using LineCollection
        segments = []
        for face in self.faces:
            if len(face) < 2: continue
            face_coords = [self.vertices[i] for i in face]
            face_coords.append(face_coords[0]) # Close the loop
            segments.append([(pt[0], pt[1]) for pt in face_coords])

        edge_col = LineCollection(segments, colors='black', linewidths=0.5, alpha=0.5)
        self.ax.add_collection(edge_col)

        # Scatter plot for interactive picking
        self.ax.scatter(coords[:, 0], coords[:, 1], c='blue', s=3, zorder=5)
        
        self.ax.autoscale()
        self.canvas.draw()

    def reset_view(self):
        if self.vertices:
            self.plot_obj()

    # ============================
    # Map Interactivity
    # ============================
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
        if self._press_event and event.xdata and event.ydata:
            dx, dy = event.xdata - self._press_event.xdata, event.ydata - self._press_event.ydata
            xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            self.canvas.draw()
            self._press_event = event

    def on_mouse_release(self, event):
        if event.button == 2: self._press_event = None

    def on_click(self, event):
        if not self.vertices or event.button != 1 or event.xdata is None or event.ydata is None: return

        coords = np.array(self.vertices)
        xy = coords[:, :2]
        z = coords[:, 2]

        click_point = np.array([event.xdata, event.ydata])
        distances = np.linalg.norm(xy - click_point, axis=1)

        threshold = 5.0
        close_indices = np.where(distances < threshold)[0]
        if close_indices.size == 0: return

        # Original User Logic: Filter points below click (in Z) to find ground anchors
        z_click = coords[close_indices, 2]
        below_indices = close_indices[z_click < np.min(z_click) + 0.01]

        chosen_index = below_indices[np.argmin(distances[below_indices])] if len(below_indices) > 0 else close_indices[np.argmin(distances[close_indices])]
        self.picked_point = self.vertices[chosen_index]
        
        # Remove previous selection markers
        for line in self.ax.lines[:]:
            if line.get_color() == 'r': line.remove()

        # Highlight picked point
        self.ax.plot(xy[chosen_index, 0], xy[chosen_index, 1], 'ro', markersize=8, zorder=10)
        self.canvas.draw()
        
        self.status_label.setText(f"📍 Picked origin:\nX: {self.picked_point[0]:.2f}\nY: {self.picked_point[1]:.2f}\nZ: {self.picked_point[2]:.2f}")

    # ============================
    # Translation Processing
    # ============================
    def set_output_directory(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Translated OBJ As", "", "OBJ Files (*.obj)")
        if file_path:
            if not file_path.lower().endswith(".obj"): file_path += ".obj"
            self.output_dir = os.path.dirname(file_path)
            self.output_file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.status_label.setText(f"Output target:\n{file_path}")

    def start_translation(self):
        if not self.picked_point:
            QMessageBox.warning(self, "Missing Data", "Please click a vertex on the map to set as the local origin.")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "Missing Data", "Please set an output directory first.")
            return

        base_name = self.output_file_name if hasattr(self, "output_file_name") and self.output_file_name else os.path.splitext(os.path.basename(self.obj_file_path))[0] + "_local"
        new_obj_path = os.path.join(self.output_dir, base_name + ".obj")
        new_mtl_name = base_name + ".mtl"
        new_mtl_path = os.path.join(self.output_dir, new_mtl_name)

        self.translate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Translating coordinates... Please wait.")

        self.trans_worker = TranslateObjWorker(
            self.obj_file_path, new_obj_path, self.picked_point, 
            self.mtl_file_path, new_mtl_path, new_mtl_name
        )
        self.trans_worker.finished.connect(self.on_translation_finished)
        self.trans_worker.start()

    def on_translation_finished(self, success, message, elapsed):
        self.translate_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText(message)
            QMessageBox.information(self, "Process Complete", f"3D model translated in {elapsed:.2f} seconds.\n\n{message}")
        else:
            self.status_label.setText("❌ Translation failed.")
            QMessageBox.critical(self, "Process Failed", f"An error occurred:\n{message}")