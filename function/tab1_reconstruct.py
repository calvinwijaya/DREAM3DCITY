from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox,
    QLineEdit, QTextEdit, QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QSizePolicy
)
from PyQt5.QtCore import Qt
import os
import subprocess

class ReconstructTab(QWidget):
    def __init__(self):
        super().__init__()
        # UI components
        layout = QVBoxLayout()

        # ===== Input Building Footprint =====
        layout.addWidget(self._bold_label("Input Building Outline"))
        layout.addWidget(QLabel(
            "The building outline files should have 'fid' attributes as Integer64 and be in Geopackage (*.gpkg) or Shapefile (*.shp) format."
        ))

        self.input_footprint = QLineEdit()
        self.btn_browse_footprint = QPushButton("Browse")
        row1 = QHBoxLayout()
        row1.addWidget(self.input_footprint)
        row1.addWidget(self.btn_browse_footprint)
        layout.addLayout(row1)

        # ===== Input Point Cloud =====
        layout.addWidget(self._bold_label("Input Point Cloud"))
        layout.addWidget(QLabel(
            "The point cloud data should be classified at least into ground (class 2) and building (class 6). Format: *.las or *.laz."
        ))

        self.input_pointcloud = QLineEdit()
        self.btn_browse_pointcloud = QPushButton("Browse")
        row2 = QHBoxLayout()
        row2.addWidget(self.input_pointcloud)
        row2.addWidget(self.btn_browse_pointcloud)
        layout.addLayout(row2)

        # ====== Output Directory =====
        layout.addWidget(self._bold_label("Output Directory"))
        layout.addWidget(QLabel("Select a folder where all output files will be saved."))

        self.output_folder = QLineEdit()
        self.btn_browse_output = QPushButton("Browse")
        row3 = QHBoxLayout()
        row3.addWidget(self.output_folder)
        row3.addWidget(self.btn_browse_output)
        layout.addLayout(row3)

        # ===== Advanced Parameters =====
        self.advanced_btn = QPushButton("Advanced Parameters ▾")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.setChecked(True)
        self.advanced_btn.clicked.connect(self.toggle_advanced)
        layout.addWidget(self.advanced_btn)

        self.advanced_group = QGroupBox()
        self.advanced_group.setVisible(True)
        advanced_layout = QVBoxLayout()
        self.advanced_inputs = {}

        self._add_advanced_input(advanced_layout, "r_line_epsilon", "max distance between line and inliers", 0.4)
        self._add_advanced_input(advanced_layout, "r_normal_k", "neighbors for normal estimation", 5, is_int=True)
        self._add_advanced_input(advanced_layout, "r_optimisation_data_term", "model detail level", 7.0, slider=True)
        self._add_advanced_input(advanced_layout, "r_plane_epsilon", "max distance plane/inliers", 0.2)
        self._add_advanced_input(advanced_layout, "r_plane_k", "neighbors for region growing", 15, is_int=True)
        self._add_advanced_input(advanced_layout, "r_plane_min_points", "minimum plane inliers", 15, is_int=True)
        self._add_advanced_input(advanced_layout, "r_plane_normal_angle", "max dot(normal1, normal2)", 0.75)

        self.advanced_group.setLayout(advanced_layout)
        layout.addWidget(self.advanced_group)

        # ===== Process Button =====
        self.btn_process = QPushButton("Process")
        self.btn_process.setStyleSheet("font-weight: bold; font-size: 20px; padding: 10px;")
        self.btn_process.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Make button fill the width
        
        # Add button to a horizontal layout to make it stretch
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_process)
        button_layout.setStretch(0, 1)

        layout.addLayout(button_layout)

        # ===== Log Console =====
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console)

        self.setLayout(layout)

        # Connect
        self.btn_browse_footprint.clicked.connect(self.browse_footprint)
        self.btn_browse_pointcloud.clicked.connect(self.browse_pointcloud)
        self.btn_browse_output.clicked.connect(self.browse_output_folder)
        self.btn_process.clicked.connect(self.run_geoflow)

    def _bold_label(self, text):
        label = QLabel(f"<b>{text}</b>")
        return label

    def _add_advanced_input(self, layout, name, tooltip, default, is_int=False, slider=False):
        row = QHBoxLayout()

        label = QLabel(f"{name}:")
        label.setToolTip(tooltip)
        label.setFixedWidth(300)  # Prevent label from squishing
        row.addWidget(label)

        if slider:
            slider_widget = QSlider(Qt.Horizontal)
            slider_widget.setMinimum(0)
            slider_widget.setMaximum(20)
            slider_widget.setSingleStep(1)
            slider_widget.setValue(int(default * 2))
            slider_widget.setTickPosition(QSlider.TicksBelow)
            slider_widget.setTickInterval(1)

            value_label = QLabel(f"{default:.1f}")
            value_label.setFixedWidth(40)
            value_label.setAlignment(Qt.AlignRight)

            slider_widget.valueChanged.connect(lambda value: value_label.setText(f"{value / 2:.1f}"))

            row.addWidget(slider_widget, stretch=1)
            row.addWidget(value_label)
            widget = slider_widget
        elif is_int:
            widget = QSpinBox()
            widget.setMaximum(9999)
            widget.setValue(default)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(widget, stretch=1)
        else:
            widget = QDoubleSpinBox()
            widget.setDecimals(6)
            widget.setSingleStep(0.01)
            widget.setValue(default)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(widget, stretch=1)

        layout.addLayout(row)
        self.advanced_inputs[name] = widget

    def toggle_advanced(self):
        show = self.advanced_btn.isChecked()
        self.advanced_group.setVisible(show)
        self.advanced_btn.setText("Advanced Parameters ▾" if show else "Advanced Parameters ▸")

    def browse_footprint(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select GPKG or SHP File", "", "Vector Files (*.gpkg *.shp)")
        if file_name:
            self.input_footprint.setText(file_name)
            self.log_console.append(f"📁 Building Footprint selected: {file_name}")

    def browse_pointcloud(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select LAS or LAZ File", "", "Point Cloud Files (*.las *.laz)")
        if file_name:
            self.input_pointcloud.setText(file_name)
            self.log_console.append(f"📁 Point Cloud selected: {file_name}")

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.output_folder.setText(folder)
            self.log_console.append(f"📁 Output directory selected: {folder}")

    def run_geoflow(self):
        fp = self.input_footprint.text()
        pc = self.input_pointcloud.text()
        out_dir = self.output_folder.text()

        if not os.path.exists(fp) or not os.path.exists(pc):
            self.log_console.append("❌ Invalid file paths.")
            return
        
        if not os.path.isdir(out_dir):
            self.log_console.append("❌ Invalid output directory.")
            return


        # 1. Run reconstruct_
        cmd1 = [
            "geof", "./function/reconstruct_.json",
            f"--input_footprint={fp}",
            f"--input_pointcloud={pc}",
            f"--output_cityjson={out_dir}/model.json",
            f"--output_obj_lod12={out_dir}/model_lod12.obj",
            f"--output_obj_lod13={out_dir}/model_lod13.obj",
            f"--output_obj_lod22={out_dir}/model_lod22.obj",
            f"--output_vector2d={out_dir}/model_2d.gpkg"
        ]

        for k, widget in self.advanced_inputs.items():
            val = widget.value()
            if isinstance(widget, QSlider):
                val = val / 2.0
            cmd1.append(f"--{k}={val}")

        # 2. Run reconstruct with parameters
        cmd2 = [
            "geof", "./function/reconstruct.json",
            f"--input_footprint={fp}",
            f"--input_pointcloud={pc}",
            f"--output_cityjson={out_dir}/model.json",
            f"--output_obj_lod12={out_dir}/model_lod12.obj",
            f"--output_obj_lod13={out_dir}/model_lod13.obj",
            f"--output_obj_lod22={out_dir}/model_lod22.obj",
            f"--output_vector2d={out_dir}/model_2d.gpkg"
        ]

        for k, widget in self.advanced_inputs.items():
            val = widget.value()
            if isinstance(widget, QSlider):
                val = val / 2.0
            cmd2.append(f"--{k}={val}")

        self.log_console.append(f"📂 Current working dir: {os.getcwd()}")
        try:
            self.log_console.append(f"🛠️ Running cmd1: {' '.join(cmd1)}")
            result1 = subprocess.run(cmd1, cwd=os.getcwd(), capture_output=True, text=True)
            self.log_console.append(result1.stdout)
            if result1.returncode != 0:
                self.log_console.append(f"❌ Error cmd1:\n{result1.stderr}")
                return

            self.log_console.append(f"🛠️ Running cmd2: {' '.join(cmd2)}")
            result2 = subprocess.run(cmd2, cwd=os.getcwd(), capture_output=True, text=True)
            self.log_console.append(result2.stdout)
            if result2.returncode != 0:
                self.log_console.append(f"❌ Error cmd2:\n{result2.stderr}")
                return

            self.log_console.append("✅ 3D Reconstruction completed successfully.")
            QMessageBox.information(self, "Process Complete", "The 3D model has been reconstructed successfully.")
        except Exception as e:
            self.log_console.append(f"❌ Exception during reconstruction:\n{e}")
            QMessageBox.information(self, "Process Failed", "The 3D model failed to generate.")
