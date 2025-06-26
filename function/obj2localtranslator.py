import os
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np

class OBJ2LocalTranslatorGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # UI Layouts
        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()

        self.load_button = QPushButton("Load OBJ")
        self.load_button.clicked.connect(self.load_obj)

        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self.reset_view)
        
        self.set_output_button = QPushButton("Set Output Directory")
        self.set_output_button.clicked.connect(self.set_output_directory)

        self.translate_button = QPushButton("Translate OBJ")
        self.translate_button.setStyleSheet("font-weight: bold; font-size: 18px; padding: 10px;")
        self.translate_button.clicked.connect(self.translate_obj)

        self.status_label = QLabel("No OBJ file loaded")
        self.status_label.setWordWrap(True)

        # Assemble left panel
        left_panel.addWidget(self.load_button)
        left_panel.addWidget(self.reset_view_button)
        left_panel.addWidget(self.set_output_button)
        left_panel.addWidget(self.translate_button)
        left_panel.addWidget(self.status_label)
        left_panel.addStretch()

        left_container = QWidget()
        left_container.setLayout(left_panel)
        left_container.setFixedWidth(250)
        main_layout.addWidget(left_container)

        # Right side: Matplotlib canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)

        # Data state
        self.obj_file_path = ""
        self.mtl_file_path = ""
        self.output_dir = ""
        self.vertices = []      # [(x, y, z)]
        self.faces = []         # [[v1, v2, v3, ...]]
        self.picked_point = None

        # Events
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.enable_panning()

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

    def reset_view(self):
        if not self.vertices:
            return
        self.plot_obj()  # Re-plot everything including limits

    def on_mouse_press(self, event):
        if event.button == 2:  # Middle mouse
            self._press_event = event

    def on_mouse_drag(self, event):
        if self._press_event and event.xdata and event.ydata:
            dx = event.xdata - self._press_event.xdata
            dy = event.ydata - self._press_event.ydata
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
            self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
            self.canvas.draw()
            self._press_event = event

    def on_mouse_release(self, event):
        if event.button == 2:
            self._press_event = None

    def load_obj(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open OBJ", "", "OBJ Files (*.obj)")
        if not file_path:
            return

        self.obj_file_path = file_path
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

        self.status_label.setText(f"Loaded OBJ with {len(self.vertices)} vertices.")
        self.plot_obj()

    def plot_obj(self):
        self.ax.clear()
        coords = np.array(self.vertices)

        # Plot edges from faces
        for face in self.faces:
            if len(face) < 2:
                continue
            face_coords = np.array([self.vertices[i] for i in face])
            x, y = face_coords[:, 0], face_coords[:, 1]
            self.ax.plot(np.append(x, x[0]), np.append(y, y[0]), 'k-', linewidth=0.8)

        # Plot vertices
        self.ax.plot(coords[:, 0], coords[:, 1], 'bo', markersize=3)
        self.ax.set_title("")
        self.ax.axis("off")  # ✅ Remove ticks, grid, axes
        self.ax.set_navigate(True)  # ✅ Allow scroll zoom & pan
        self.canvas.draw()

    def on_click(self, event):
        if not self.vertices or event.xdata is None or event.ydata is None:
            return

        coords = np.array(self.vertices)
        xy = coords[:, :2]
        z = coords[:, 2]

        click_point = np.array([event.xdata, event.ydata])
        distances = np.linalg.norm(xy - click_point, axis=1)

        # Find candidates within radius
        threshold = 5
        close_indices = np.where(distances < threshold)[0]

        if close_indices.size == 0:
            return

        # Further filter to points below click (in Z)
        z_click = coords[close_indices, 2]
        below_indices = close_indices[z_click < np.min(z_click) + 0.01]  # or stricter

        # If some are below, pick closest among them
        if len(below_indices) > 0:
            chosen_index = below_indices[np.argmin(distances[below_indices])]
        else:
            chosen_index = close_indices[np.argmin(distances[close_indices])]

        self.picked_point = self.vertices[chosen_index]
        self.status_label.setText(f"Picked point: {self.picked_point}")

        # Draw only the highlight, preserve zoom/pan
        for line in self.ax.lines[:]:
            if line.get_color() == 'r':
                line.remove()

        self.ax.plot(xy[chosen_index, 0], xy[chosen_index, 1], 'ro', markersize=6)
        self.canvas.draw()

    def set_output_directory(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Translated OBJ As",
            "",
            "OBJ Files (*.obj)"
        )
        if file_path:
            if not file_path.lower().endswith(".obj"):
                file_path += ".obj"
            self.output_dir = os.path.dirname(file_path)
            self.output_file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.status_label.setText(f"Output set: {file_path}")

    def translate_obj(self):
        if not self.picked_point:
            self.status_label.setText("No point picked yet.")
            return
        if not self.output_dir:
            self.status_label.setText("Output directory not set.")
            return

        if not hasattr(self, "output_file_name"):
            base_name = os.path.splitext(os.path.basename(self.obj_file_path))[0] + "_local"
        else:
            base_name = self.output_file_name

        new_obj_path = os.path.join(self.output_dir, base_name + ".obj")
        new_mtl_name = base_name + ".mtl"

        with open(self.obj_file_path, 'r') as infile, open(new_obj_path, 'w') as outfile:
            for line in infile:
                if line.startswith("v "):
                    parts = line.strip().split()
                    x, y, z = map(float, parts[1:])
                    x -= self.picked_point[0]
                    y -= self.picked_point[1]
                    z -= self.picked_point[2]
                    outfile.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                elif line.startswith("mtllib"):
                    outfile.write(f"mtllib {new_mtl_name}\n")
                else:
                    outfile.write(line)

        if self.mtl_file_path and os.path.exists(self.mtl_file_path):
            new_mtl_path = os.path.join(self.output_dir, new_mtl_name)
            shutil.copy(self.mtl_file_path, new_mtl_path)

        self.status_label.setText(f"Translated OBJ saved to: {new_obj_path}")
        QMessageBox.information(self, "Process Complete", "The 3D model has been translated successfully.")