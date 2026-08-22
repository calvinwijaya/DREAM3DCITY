import os
import glob
import time
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox,
    QLineEdit, QTextEdit, QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QSizePolicy,
    QComboBox, QCheckBox, QStackedWidget, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class ReconstructionWorker(QThread):
    """
    Background worker thread to execute Geoflow or Roofer commands
    without blocking the PyQt user interface.
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, float)  # (success, message, elapsed_seconds)

    def __init__(self, algo, fp, pc, out_dir, geoflow_params=None, roofer_params=None):
        super().__init__()
        self.algo = algo
        self.fp = fp
        self.pc = pc
        self.out_dir = out_dir
        self.geoflow_params = geoflow_params or {}
        self.roofer_params = roofer_params or {}

    def run(self):
        start_time = time.perf_counter()
        try:
            if self.algo == "Geoflow":
                success, msg = self._run_geoflow()
            else:
                success, msg = self._run_roofer()

            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(success, msg, elapsed)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.finished_signal.emit(False, str(e), elapsed)

    def _stream_process(self, cmd):
        """Executes subprocess and streams console logs in real time."""
        self.log_signal.emit(f"🛠️ Executing: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        for line in process.stdout:
            self.log_signal.emit(line.rstrip())

        process.wait()
        return process.returncode

    def _run_geoflow(self):
        # Step 1: reconstruct_
        cmd1 = [
            "geof", "./function/reconstruct_.json",
            f"--input_footprint={self.fp}",
            f"--input_pointcloud={self.pc}",
            f"--output_cityjson={self.out_dir}/model.json",
            f"--output_obj_lod12={self.out_dir}/model_lod12.obj",
            f"--output_obj_lod13={self.out_dir}/model_lod13.obj",
            f"--output_obj_lod22={self.out_dir}/model_lod22.obj",
            f"--output_vector2d={self.out_dir}/model_2d.gpkg"
        ]
        for k, v in self.geoflow_params.items():
            cmd1.append(f"--{k}={v}")

        if self._stream_process(cmd1) != 0:
            return False, "Geoflow initialization step (reconstruct_) failed."

        # Step 2: reconstruct
        cmd2 = [
            "geof", "./function/reconstruct.json",
            f"--input_footprint={self.fp}",
            f"--input_pointcloud={self.pc}",
            f"--output_cityjson={self.out_dir}/model.json",
            f"--output_obj_lod12={self.out_dir}/model_lod12.obj",
            f"--output_obj_lod13={self.out_dir}/model_lod13.obj",
            f"--output_obj_lod22={self.out_dir}/model_lod22.obj",
            f"--output_vector2d={self.out_dir}/model_2d.gpkg"
        ]
        for k, v in self.geoflow_params.items():
            cmd2.append(f"--{k}={v}")

        if self._stream_process(cmd2) != 0:
            return False, "Geoflow reconstruction step failed."

        return True, "Geoflow finished successfully."

    def _run_roofer(self):
        roofer_exe = os.path.join(".", "function", "roofer", "bin", "roofer.exe")
        if not os.path.exists(roofer_exe):
            return False, f"Roofer executable not found at: {roofer_exe}"

        cmd = [roofer_exe]

        # LoD Flags
        if self.roofer_params.get("lod12"): cmd.append("--lod12")
        if self.roofer_params.get("lod13"): cmd.append("--lod13")
        if self.roofer_params.get("lod22"): cmd.append("--lod22")

        # Numeric Flags
        for key in ["complexity-factor", "plane-detect-k", "plane-detect-min-points", 
                    "plane-detect-epsilon", "cellsize", "bld-class", "grnd-class"]:
            if key in self.roofer_params:
                cmd.extend([f"--{key}", str(self.roofer_params[key])])

        # Positional Arguments
        cmd.extend([self.pc, self.fp, self.out_dir])

        base_name = os.path.splitext(os.path.basename(self.fp))[0]
        existing_jsonls = {os.path.basename(f) for f in glob.glob(os.path.join(self.out_dir, "*.city.jsonl"))}

        if self._stream_process(cmd) != 0:
            return False, "Roofer binary execution returned an error."

        # Parse & Convert Output
        all_jsonls = {os.path.basename(f) for f in glob.glob(os.path.join(self.out_dir, "*.city.jsonl"))}
        new_jsonls = all_jsonls - existing_jsonls

        if new_jsonls:
            from function.cityjsonl2obj import process_roofer_output
            for idx, gen_file_name in enumerate(new_jsonls):
                gen_file_path = os.path.join(self.out_dir, gen_file_name)
                target_base = base_name if len(new_jsonls) == 1 else f"{base_name}_{idx}"
                target_jsonl_path = os.path.join(self.out_dir, f"{target_base}.city.jsonl")

                if gen_file_path != target_jsonl_path:
                    if os.path.exists(target_jsonl_path):
                        os.remove(target_jsonl_path)
                    os.rename(gen_file_path, target_jsonl_path)

                self.log_signal.emit(f"🔄 Converting {target_base}.city.jsonl to standard CityJSON and OBJ...")
                ok, msg = process_roofer_output(target_jsonl_path, self.out_dir, target_base)
                if ok:
                    self.log_signal.emit(f"✅ Generated {target_base}.json, {target_base}.obj, {target_base}.mtl")
                else:
                    self.log_signal.emit(f"❌ Conversion failed for {target_base}: {msg}")

        return True, "Roofer execution and CityJSON/OBJ conversions completed."


class ReconstructTab(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        # ===== Algorithm Selection Card =====
        layout.addWidget(self._bold_label("Algorithm Selection"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["Geoflow", "Roofer"])
        self.algo_combo.currentIndexChanged.connect(self.change_algorithm)
        layout.addWidget(self.algo_combo)

        # ===== Input Building Footprint =====
        layout.addWidget(self._bold_label("Input Building Outline (*.gpkg, *.shp)"))
        self.input_footprint = QLineEdit()
        self.input_footprint.setPlaceholderText("Select GPKG or Shapefile...")
        self.btn_browse_footprint = QPushButton("Browse")
        
        row1 = QHBoxLayout()
        row1.addWidget(self.input_footprint)
        row1.addWidget(self.btn_browse_footprint)
        layout.addLayout(row1)

        # ===== Input Point Cloud =====
        layout.addWidget(self._bold_label("Input Point Cloud (*.las, *.laz)"))
        self.input_pointcloud = QLineEdit()
        self.input_pointcloud.setPlaceholderText("Select LAS or LAZ point cloud...")
        self.btn_browse_pointcloud = QPushButton("Browse")
        
        row2 = QHBoxLayout()
        row2.addWidget(self.input_pointcloud)
        row2.addWidget(self.btn_browse_pointcloud)
        layout.addLayout(row2)

        # ===== Output Directory =====
        layout.addWidget(self._bold_label("Output Directory"))
        self.output_folder = QLineEdit()
        self.output_folder.setPlaceholderText("Select destination directory...")
        self.btn_browse_output = QPushButton("Browse")
        
        row3 = QHBoxLayout()
        row3.addWidget(self.output_folder)
        row3.addWidget(self.btn_browse_output)
        layout.addLayout(row3)

        # ===== Advanced Parameters Section =====
        self.advanced_btn = QPushButton("Advanced Parameters ▾")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.setChecked(True)
        self.advanced_btn.setStyleSheet("text-align: left; font-weight: bold; background: #F1F5F9; border: 1px solid #E2E8F0;")
        self.advanced_btn.clicked.connect(self.toggle_advanced)
        layout.addWidget(self.advanced_btn)

        self.advanced_group = QGroupBox()
        advanced_layout = QVBoxLayout()

        self.param_stack = QStackedWidget()

        # --- Geoflow Parameters ---
        self.geoflow_widget = QWidget()
        geoflow_layout = QVBoxLayout(self.geoflow_widget)
        geoflow_layout.setContentsMargins(0, 0, 0, 0)
        self.geoflow_inputs = {}

        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_line_epsilon", "Max distance between line and inliers", 0.4)
        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_normal_k", "Neighbors for normal estimation", 5, is_int=True)
        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_optimisation_data_term", "Model detail level", 7.0, slider=True)
        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_plane_epsilon", "Max distance plane/inliers", 0.2)
        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_plane_k", "Neighbors for region growing", 15, is_int=True)
        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_plane_min_points", "Minimum plane inliers", 15, is_int=True)
        self._add_numeric_input(geoflow_layout, self.geoflow_inputs, "r_plane_normal_angle", "Max dot(normal1, normal2)", 0.75)

        # --- Roofer Parameters ---
        self.roofer_widget = QWidget()
        roofer_layout = QVBoxLayout(self.roofer_widget)
        roofer_layout.setContentsMargins(0, 0, 0, 0)
        self.roofer_inputs = {}

        self._add_checkbox_input(roofer_layout, self.roofer_inputs, "lod12", "Generate LoD 1.2 geometries", False)
        self._add_checkbox_input(roofer_layout, self.roofer_inputs, "lod13", "Generate LoD 1.3 geometries", False)
        self._add_checkbox_input(roofer_layout, self.roofer_inputs, "lod22", "Generate LoD 2.2 geometries", True)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "complexity-factor", "Balance fidelity (1.0) and smoothness (0.0)", 0.888)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "plane-detect-k", "Neighbors used to grow planes", 15, is_int=True)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "plane-detect-min-points", "Minimum points in a detected plane", 15, is_int=True)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "plane-detect-epsilon", "Maximum plane fitting distance (m)", 0.3)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "cellsize", "Point cloud analysis cell size (m)", 0.5)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "bld-class", "Building LAS classification code", 6, is_int=True)
        self._add_numeric_input(roofer_layout, self.roofer_inputs, "grnd-class", "Ground LAS classification code", 2, is_int=True)

        self.param_stack.addWidget(self.geoflow_widget)
        self.param_stack.addWidget(self.roofer_widget)

        advanced_layout.addWidget(self.param_stack)
        self.advanced_group.setLayout(advanced_layout)
        layout.addWidget(self.advanced_group)

        # ===== Processing Button & Indeterminate Progress Bar =====
        self.btn_process = QPushButton("Start Reconstruction")
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
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #94A3B8;
                color: #F1F5F9;
            }
        """)
        self.btn_process.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.btn_process)

        # Indeterminate Progress Bar (Hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Continuous pulse animation
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E2E8F0;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ===== Log Console =====
        layout.addWidget(self._bold_label("Execution Log"))
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 12px;
                border-radius: 6px;
                padding: 8px;
                border: 1px solid #334155;
            }
        """)
        self.log_console.setMinimumHeight(180)
        layout.addWidget(self.log_console)

        self.setLayout(layout)

        # Signal Connections
        self.btn_browse_footprint.clicked.connect(self.browse_footprint)
        self.btn_browse_pointcloud.clicked.connect(self.browse_pointcloud)
        self.btn_browse_output.clicked.connect(self.browse_output_folder)
        self.btn_process.clicked.connect(self.start_processing)

    def _bold_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #334155;")
        return label

    def change_algorithm(self, index):
        self.param_stack.setCurrentIndex(index)

    def _add_numeric_input(self, layout, target_dict, name, tooltip, default, is_int=False, slider=False):
        row = QHBoxLayout()
        label = QLabel(f"{name}:")
        label.setToolTip(tooltip)
        label.setFixedWidth(240)
        row.addWidget(label)

        if slider:
            slider_widget = QSlider(Qt.Orientation.Horizontal)
            slider_widget.setMinimum(0)
            slider_widget.setMaximum(20)
            slider_widget.setSingleStep(1)
            slider_widget.setValue(int(default * 2))
            slider_widget.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider_widget.setTickInterval(1)

            value_label = QLabel(f"{default:.1f}")
            value_label.setFixedWidth(40)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            slider_widget.valueChanged.connect(lambda val: value_label.setText(f"{val / 2:.1f}"))

            row.addWidget(slider_widget, stretch=1)
            row.addWidget(value_label)
            widget = slider_widget
        elif is_int:
            widget = QSpinBox()
            widget.setMaximum(99999)
            widget.setValue(default)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(widget, stretch=1)
        else:
            widget = QDoubleSpinBox()
            widget.setDecimals(4)
            widget.setSingleStep(0.05)
            widget.setValue(default)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(widget, stretch=1)

        layout.addLayout(row)
        target_dict[name] = widget

    def _add_checkbox_input(self, layout, target_dict, name, tooltip, default_checked):
        row = QHBoxLayout()
        label = QLabel(f"{name}:")
        label.setToolTip(tooltip)
        label.setFixedWidth(240)

        widget = QCheckBox()
        widget.setChecked(default_checked)

        row.addWidget(label)
        row.addWidget(widget, stretch=1)
        layout.addLayout(row)
        target_dict[name] = widget

    def toggle_advanced(self):
        show = self.advanced_btn.isChecked()
        self.advanced_group.setVisible(show)
        self.advanced_btn.setText("Advanced Parameters ▾" if show else "Advanced Parameters ▸")

    def browse_footprint(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Building Outline", "", "Vector Files (*.gpkg *.shp)")
        if file_name:
            self.input_footprint.setText(file_name)
            self.log_console.append(f"📁 Building footprint selected: {file_name}")

    def browse_pointcloud(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Point Cloud", "", "Point Cloud Files (*.las *.laz)")
        if file_name:
            self.input_pointcloud.setText(file_name)
            self.log_console.append(f"📁 Point cloud selected: {file_name}")

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.output_folder.setText(folder)
            self.log_console.append(f"📁 Output folder selected: {folder}")

    def start_processing(self):
        fp = self.input_footprint.text().strip()
        pc = self.input_pointcloud.text().strip()
        out_dir = self.output_folder.text().strip()

        if not os.path.exists(fp) or not os.path.exists(pc):
            QMessageBox.warning(self, "Invalid Input", "Please provide valid footprint and point cloud file paths.")
            return

        if not os.path.isdir(out_dir):
            QMessageBox.warning(self, "Invalid Output", "Please select a valid output directory.")
            return

        # Prepare parameters
        algo = self.algo_combo.currentText()
        geoflow_params = {}
        roofer_params = {}

        if algo == "Geoflow":
            for k, widget in self.geoflow_inputs.items():
                val = widget.value()
                if isinstance(widget, QSlider):
                    val = val / 2.0
                geoflow_params[k] = val
        else:
            for k, widget in self.roofer_inputs.items():
                if isinstance(widget, QCheckBox):
                    roofer_params[k] = widget.isChecked()
                else:
                    roofer_params[k] = widget.value()

        # UI state: active processing
        self.btn_process.setEnabled(False)
        self.btn_process.setText("Processing Reconstruction...")
        self.progress_bar.setVisible(True)
        self.log_console.append(f"\n🚀 Starting {algo} 3D reconstruction pipeline...")

        # Initialize and launch background thread
        self.worker = ReconstructionWorker(algo, fp, pc, out_dir, geoflow_params, roofer_params)
        self.worker.log_signal.connect(self.log_console.append)
        self.worker.finished_signal.connect(self.on_processing_finished)
        self.worker.start()

    def on_processing_finished(self, success, message, elapsed_seconds):
        # UI state: reset
        self.btn_process.setEnabled(True)
        self.btn_process.setText("Start Reconstruction")
        self.progress_bar.setVisible(False)

        if success:
            finish_msg = f"✅ 3D Reconstruction completed successfully in {elapsed_seconds:.2f} seconds."
            self.log_console.append(finish_msg)
            QMessageBox.information(self, "Process Complete", finish_msg)
        else:
            self.log_console.append(f"❌ Process failed after {elapsed_seconds:.2f} seconds:\n{message}")
            QMessageBox.critical(self, "Process Failed", f"Reconstruction failed:\n{message}")