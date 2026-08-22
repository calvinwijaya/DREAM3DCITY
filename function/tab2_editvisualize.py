import sys
import os
import json
import shutil
import vtk
import copy
import tempfile
import numpy as np
import geopandas as gpd
import laspy
from collections import OrderedDict
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QSizePolicy, QComboBox, QCheckBox, QGroupBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


# ==========================================
# Background Workers for Heavy File Loading
# ==========================================
class LasLoaderWorker(QThread):
    finished = pyqtSignal(object, object, str)  # (building_data, ground_data, message)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            las = laspy.read(self.file_path)
            ground_mask = las.classification == 2
            building_mask = las.classification == 6

            if not np.any(ground_mask) and not np.any(building_mask):
                self.finished.emit(None, None, "No ground (2) or building (6) points found.")
                return

            def extract_data(mask):
                if not np.any(mask): return None
                x, y, z = las.x[mask], las.y[mask], las.z[mask]
                r, g, b = las.red[mask], las.green[mask], las.blue[mask]
                
                # Normalize RGB
                max_val = np.max([r.max(), g.max(), b.max()])
                if max_val > 255:
                    r = (r / 256).astype(np.uint8)
                    g = (g / 256).astype(np.uint8)
                    b = (b / 256).astype(np.uint8)
                
                return {"x": x, "y": y, "z": z, "r": r, "g": g, "b": b}

            self.finished.emit(extract_data(building_mask), extract_data(ground_mask), "Success")
        except Exception as e:
            self.finished.emit(None, None, f"Error: {str(e)}")


class GeoJsonLoaderWorker(QThread):
    finished = pyqtSignal(list, str)  # (list_of_gdfs, message)

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        try:
            gdfs = [gpd.read_file(path) for path in self.file_paths]
            self.finished.emit(gdfs, "Success")
        except Exception as e:
            self.finished.emit([], f"Error: {str(e)}")


class JsonLoaderWorker(QThread):
    finished = pyqtSignal(dict, str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            data["_input_filename"] = self.file_path
            self.finished.emit(data, "Success")
        except Exception as e:
            self.finished.emit({}, f"Error: {str(e)}")


# ==========================================
# Main Visualization Tab
# ==========================================
class VisualizeTab(QWidget):
    def __init__(self, folder=None, cityjson_file=None):
        super().__init__()
        self.models = {}
        self.selected_actors = set()
        self.cityjson_data = None
        self.outline_geojsons = []
        
        self.cityjson_actors = []
        self.outline_actors = []
        self.obj_actors = []
        
        self.clipping_box_widget = None
        self.clipping_box_enabled = False

        self.building_actor = None
        self.ground_actor = None
        self.original_building_polydata = None
        self.original_ground_polydata = None
        self.downsampled_building_polydata = None
        self.downsampled_ground_polydata = None

        self.last_clipping_planes = None
        self.last_clipping_bounds = None
        self.fid_dtm_map = {}
        self.export_dir = ""

        self.setup_ui()
        self.setup_vtk()

        if cityjson_file:
            self.load_cityjson_file_dialog(cityjson_file)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === Left Panel ===
        left_panel_widget = QWidget()
        left_panel_widget.setFixedWidth(280)
        left_panel_widget.setStyleSheet("background-color: #F8FAFC; border-right: 1px solid #E2E8F0;")
        left_panel = QVBoxLayout(left_panel_widget)
        left_panel.setContentsMargins(12, 12, 12, 12)
        left_panel.setSpacing(12)

        # 1. Load Data Group
        load_group = QGroupBox("1. Load Data")
        load_layout = QVBoxLayout()
        
        self.load_button = self._create_btn("Load CityJSON", primary=True)
        self.load_pointcloud_button = self._create_btn("Load Point Cloud", primary=True)
        self.load_outline_button = self._create_btn("Load Building Outline", primary=True)
        self.load_obj_button = self._create_btn("Load OBJ", primary=True)
        
        self.load_button.clicked.connect(lambda: self._trigger_file_dialog("cityjson"))
        self.load_pointcloud_button.clicked.connect(lambda: self._trigger_file_dialog("las"))
        self.load_outline_button.clicked.connect(lambda: self._trigger_file_dialog("geojson"))
        self.load_obj_button.clicked.connect(lambda: self._trigger_file_dialog("obj"))
        
        load_layout.addWidget(self.load_button)
        load_layout.addWidget(self.load_pointcloud_button)
        load_layout.addWidget(self.load_outline_button)
        load_layout.addWidget(self.load_obj_button)
        load_group.setLayout(load_layout)
        left_panel.addWidget(load_group)

        # 2. Export Data Group
        export_group = QGroupBox("2. Export Data")
        export_layout = QVBoxLayout()
        self.choose_dir_button = self._create_btn("Choose Export Directory")
        self.choose_dir_button.clicked.connect(self.choose_export_directory)
        
        self.lod_dropdown = QComboBox()
        self.lod_dropdown.addItems(["1.2", "1.3", "2.2"])
        
        self.export_button = self._create_btn("Export Selected Data", primary=True)
        self.export_button.clicked.connect(self.export_selected_data)

        export_layout.addWidget(self.choose_dir_button)
        export_layout.addWidget(QLabel("OBJ Export LOD:"))
        export_layout.addWidget(self.lod_dropdown)
        export_layout.addWidget(self.export_button)
        export_group.setLayout(export_layout)
        left_panel.addWidget(export_group)

        # 3. Visualization Tools Group
        viz_group = QGroupBox("3. Slicing Tools")
        viz_layout = QVBoxLayout()
        self.slicing_button = self._create_btn("Toggle Slicing Box")
        self.slicing_button.clicked.connect(self.toggle_slicing_box)
        self.restore_box_button = self._create_btn("Restore Bounding Box")
        self.restore_box_button.clicked.connect(self.restore_clipping_box)
        viz_layout.addWidget(self.slicing_button)
        viz_layout.addWidget(self.restore_box_button)
        viz_group.setLayout(viz_layout)
        left_panel.addWidget(viz_group)

        # 4. Remove Data Group
        remove_group = QGroupBox("4. Remove Data")
        remove_layout = QVBoxLayout()
        self.remove_cityjson_button = self._create_btn("Remove CityJSON", danger=True)
        self.remove_pointcloud_button = self._create_btn("Remove Point Cloud", danger=True)
        self.remove_outline_button = self._create_btn("Remove Outline", danger=True)
        self.remove_obj_button = self._create_btn("Remove OBJ", danger=True)

        self.remove_cityjson_button.clicked.connect(self.remove_cityjson)
        self.remove_pointcloud_button.clicked.connect(self.remove_pointcloud)
        self.remove_outline_button.clicked.connect(self.remove_building_outline)
        self.remove_obj_button.clicked.connect(self.remove_obj)
        
        remove_layout.addWidget(self.remove_cityjson_button)
        remove_layout.addWidget(self.remove_pointcloud_button)
        remove_layout.addWidget(self.remove_outline_button)
        remove_layout.addWidget(self.remove_obj_button)
        remove_group.setLayout(remove_layout)
        left_panel.addWidget(remove_group)

        # Status Label
        self.status_label = QLabel("Ready. Load files to visualize.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #64748B; font-size: 11px; margin-top: 10px;")
        left_panel.addWidget(self.status_label)
        left_panel.addStretch()

        # === Right Panel (VTK) ===
        vtk_container = QWidget()
        vtk_layout = QVBoxLayout(vtk_container)
        vtk_layout.setContentsMargins(0, 0, 0, 0)
        self.vtk_widget = QVTKRenderWindowInteractor(vtk_container)
        self.vtk_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vtk_layout.addWidget(self.vtk_widget)

        # === Floating Overlays ===
        self._setup_floating_overlays()

        main_layout.addWidget(left_panel_widget)
        main_layout.addWidget(vtk_container)

    def _create_btn(self, text, primary=False, danger=False):
        btn = QPushButton(text)
        if primary:
            btn.setStyleSheet("QPushButton { background-color: #2563EB; color: white; border-radius: 4px; padding: 6px; } QPushButton:hover { background-color: #1D4ED8; }")
        elif danger:
            btn.setStyleSheet("QPushButton { background-color: #FEE2E2; color: #DC2626; border: 1px solid #FECACA; border-radius: 4px; padding: 6px; } QPushButton:hover { background-color: #FECACA; }")
        else:
            btn.setStyleSheet("QPushButton { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px; } QPushButton:hover { background-color: #F1F5F9; }")
        return btn

    def _setup_floating_overlays(self):
        overlay_style = """
            QWidget { background-color: rgba(255, 255, 255, 0.95); border: 1px solid #E2E8F0; border-radius: 8px; }
            QPushButton { border: none; background: transparent; font-weight: bold; color: #334155; text-align: left; padding: 5px; }
            QPushButton:hover { color: #2563EB; }
            QCheckBox { font-size: 12px; padding: 2px; background: transparent; border: none; }
        """
        # Layers Overlay
        self.overlay_widget = QWidget(self.vtk_widget)
        self.overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay_widget.setStyleSheet(overlay_style)
        self.overlay_widget.setFixedSize(200, 180)
        
        ol = QVBoxLayout(self.overlay_widget)
        ol.setContentsMargins(10, 10, 10, 10)
        
        self.toggle_overlay_button = QPushButton("▼ Layers")
        self.toggle_overlay_button.clicked.connect(self.toggle_layer_visibility)
        ol.addWidget(self.toggle_overlay_button)

        self.overlay_content = QWidget()
        self.overlay_content.setStyleSheet("border: none;")
        ocl = QVBoxLayout(self.overlay_content)
        ocl.setContentsMargins(0, 0, 0, 0)
        
        self.cityjson_checkbox = QCheckBox("Show CityJSON")
        self.cityjson_checkbox.setChecked(True)
        self.cityjson_checkbox.stateChanged.connect(self.toggle_cityjson_visibility)
        
        self.building_checkbox = QCheckBox("Show Building Points")
        self.building_checkbox.setChecked(True)
        self.building_checkbox.stateChanged.connect(self.toggle_building_points)
        
        self.ground_checkbox = QCheckBox("Show Ground Points")
        self.ground_checkbox.setChecked(True)
        self.ground_checkbox.stateChanged.connect(self.toggle_ground_points)
        
        self.outline_checkbox = QCheckBox("Show Building Outline")
        self.outline_checkbox.setChecked(True)
        self.outline_checkbox.stateChanged.connect(self.toggle_outline_visibility)
        
        self.obj_checkbox = QCheckBox("Show OBJ")
        self.obj_checkbox.setChecked(True)
        self.obj_checkbox.stateChanged.connect(self.toggle_obj_visibility)
        
        ocl.addWidget(self.cityjson_checkbox)
        ocl.addWidget(self.building_checkbox)
        ocl.addWidget(self.ground_checkbox)
        ocl.addWidget(self.outline_checkbox)
        ocl.addWidget(self.obj_checkbox)
        ol.addWidget(self.overlay_content)

        # View Controls Overlay
        self.view_overlay_widget = QWidget(self.vtk_widget)
        self.view_overlay_widget.setStyleSheet(overlay_style)
        self.view_overlay_widget.setFixedSize(140, 210)
        
        vl = QVBoxLayout(self.view_overlay_widget)
        vl.setContentsMargins(10, 10, 10, 10)
        
        self.toggle_view_button = QPushButton("▶ View Controls")
        self.toggle_view_button.clicked.connect(self.toggle_view_visibility)
        vl.addWidget(self.toggle_view_button)

        self.view_content = QWidget()
        self.view_content.setStyleSheet("border: none;")
        vcl = QVBoxLayout(self.view_content)
        vcl.setContentsMargins(0, 0, 0, 0)
        
        btn_style = "QPushButton { background: #F1F5F9; border-radius: 4px; padding: 4px; text-align: center; } QPushButton:hover { background: #E2E8F0; }"
        for label, func in [("Top", self.reset_view_top), ("Bottom", self.reset_view_bottom), 
                            ("Front", self.reset_view_front), ("Back", self.reset_view_back), 
                            ("Left", self.reset_view_left), ("Right", self.reset_view_right)]:
            b = QPushButton(label)
            b.setStyleSheet(btn_style)
            b.clicked.connect(func)
            vcl.addWidget(b)
            
        self.view_content.setVisible(False)
        self.view_overlay_widget.setFixedHeight(40)
        vl.addWidget(self.view_content)

    def setup_vtk(self):
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.95, 0.95, 0.95)  # Modern light gray VTK background
        self.render_window = self.vtk_widget.GetRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        self.interactor = self.vtk_widget
        self.interactor.SetRenderWindow(self.render_window)
        
        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.0005)
        self.interactor.AddObserver("LeftButtonPressEvent", self.on_mouse_click)

        self.interactor.Initialize()
        QTimer.singleShot(0, self.interactor.Start)
        self.add_axes()

        style = vtk.vtkInteractorStyleTrackballCamera()
        style.OnLeftButtonDown = lambda obj, evt: None  # Disable native rotation interference
        self.interactor.SetInteractorStyle(style)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 15
        if self.vtk_widget:
            if hasattr(self, 'overlay_widget') and self.overlay_widget:
                self.overlay_widget.move(self.vtk_widget.width() - self.overlay_widget.width() - margin, margin)
            if hasattr(self, 'view_overlay_widget') and self.view_overlay_widget:
                self.view_overlay_widget.move(margin, margin)

    # ============================
    # UI Toggles & View Controls
    # ============================
    def toggle_layer_visibility(self):
        expanded = self.overlay_content.isVisible()
        self.overlay_content.setVisible(not expanded)
        self.toggle_overlay_button.setText("▶ Layers" if expanded else "▼ Layers")
        self.overlay_widget.setFixedHeight(40 if expanded else 180)

    def toggle_view_visibility(self):
        expanded = self.view_content.isVisible()
        self.view_content.setVisible(not expanded)
        self.toggle_view_button.setText("▶ View Controls" if expanded else "▼ View Controls")
        self.view_overlay_widget.setFixedHeight(40 if expanded else 240)

    def set_camera_view(self, position, view_up):
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(*position)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(*view_up)
        self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()

    def reset_view_top(self): self.set_camera_view((0, 0, 1), (0, 1, 0))
    def reset_view_bottom(self): self.set_camera_view((0, 0, -1), (0, -1, 0))
    def reset_view_front(self): self.set_camera_view((0, -1, 0), (0, 0, 1))
    def reset_view_back(self): self.set_camera_view((0, 1, 0), (0, 0, 1))
    def reset_view_left(self): self.set_camera_view((-1, 0, 0), (0, 0, 1))
    def reset_view_right(self): self.set_camera_view((1, 0, 0), (0, 0, 1))

    def add_axes(self):
        axes = vtk.vtkAxesActor()
        orientation_marker = vtk.vtkOrientationMarkerWidget()
        orientation_marker.SetOrientationMarker(axes)
        orientation_marker.SetInteractor(self.interactor)
        orientation_marker.SetViewport(0.0, 0.0, 0.2, 0.2)
        orientation_marker.SetEnabled(1)
        orientation_marker.InteractiveOff()
        orientation_marker.SetOutlineColor(0.5, 0.5, 0.5)
        self.orientation_marker_widget = orientation_marker

    # ============================
    # Checkbox Interactions
    # ============================
    def toggle_cityjson_visibility(self, state):
        visible = state == Qt.CheckState.Checked.value
        for actor in self.cityjson_actors: actor.SetVisibility(visible)
        self.render_window.Render()

    def toggle_building_points(self, state):
        if self.building_actor:
            self.building_actor.SetVisibility(state == Qt.CheckState.Checked.value)
            self.render_window.Render()

    def toggle_ground_points(self, state):
        if self.ground_actor:
            self.ground_actor.SetVisibility(state == Qt.CheckState.Checked.value)
            self.render_window.Render()

    def toggle_outline_visibility(self, state):
        visible = state == Qt.CheckState.Checked.value
        for actor in self.outline_actors: actor.SetVisibility(visible)
        self.render_window.Render()

    def toggle_obj_visibility(self, state):
        visible = state == Qt.CheckState.Checked.value
        for actor in self.obj_actors: actor.SetVisibility(visible)
        self.render_window.Render()

    # ============================
    # Picking Logic
    # ============================
    def on_mouse_click(self, obj, event):
        click_pos = self.interactor.GetEventPosition()
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        actor = self.picker.GetActor()

        excluded = [self.ground_actor, self.building_actor]

        if actor and actor not in excluded:
            if actor in self.selected_actors:
                actor.GetMapper().ScalarVisibilityOn()
                actor.GetProperty().SetColor(0.2, 0.6, 1.0)
                self.selected_actors.remove(actor)
            else:
                actor.GetMapper().ScalarVisibilityOff()
                actor.GetProperty().SetColor(1.0, 1.0, 0.0)
                self.selected_actors.add(actor)

            self.renderer.ResetCameraClippingRange()
            self.render_window.Render()

    # ============================
    # Loading Dialogs & Threading
    # ============================
    def _trigger_file_dialog(self, ftype):
        if ftype == "cityjson":
            path, _ = QFileDialog.getOpenFileName(self, "Open CityJSON", "", "CityJSON Files (*.json *.city.json)")
            if path: self._load_cityjson_threaded(path)
        elif ftype == "las":
            path, _ = QFileDialog.getOpenFileName(self, "Open LAS", "", "LAS Files (*.las *.laz)")
            if path: self._load_las_threaded(path)
        elif ftype == "geojson":
            paths, _ = QFileDialog.getOpenFileNames(self, "Open Outline", "", "GeoJSON (*.geojson *.json)")
            if paths: self._load_geojson_threaded(paths)
        elif ftype == "obj":
            path, _ = QFileDialog.getOpenFileName(self, "Open OBJ", "", "OBJ Files (*.obj)")
            if path: self.read_obj_with_swizzle(path)

    def _load_cityjson_threaded(self, file_path):
        self.status_label.setText("Loading CityJSON in background...")
        self.worker = JsonLoaderWorker(file_path)
        self.worker.finished.connect(self._on_cityjson_loaded)
        self.worker.start()

    def _on_cityjson_loaded(self, data, msg):
        if not data:
            self.status_label.setText(msg)
            return
            
        self.remove_cityjson()
        self.cityjson_data = data
        self._build_cityjson_models(data)
        self.status_label.setText("✅ CityJSON successfully rendered.")

    def _load_las_threaded(self, file_path):
        self.status_label.setText("Reading point cloud in background...")
        self.worker = LasLoaderWorker(file_path)
        self.worker.finished.connect(self._on_las_loaded)
        self.worker.start()

    def _on_las_loaded(self, bldg, ground, msg):
        if msg != "Success":
            self.status_label.setText(msg)
            return
        
        self.remove_pointcloud()
        
        def dict_to_poly(d):
            if not d: return None
            points = vtk.vtkPoints()
            colors = vtk.vtkUnsignedCharArray()
            colors.SetNumberOfComponents(3)
            colors.SetName("Colors")
            
            for i in range(len(d["x"])):
                points.InsertNextPoint(d["x"][i], d["y"][i], d["z"][i])
                colors.InsertNextTuple3(d["r"][i], d["g"][i], d["b"][i])
                
            poly = vtk.vtkPolyData()
            poly.SetPoints(points)
            poly.GetPointData().SetScalars(colors)
            return poly
            
        if bldg:
            self.original_building_polydata = dict_to_poly(bldg)
            glyph = vtk.vtkVertexGlyphFilter()
            glyph.SetInputData(self.original_building_polydata)
            glyph.Update()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(glyph.GetOutputPort())
            self.building_actor = vtk.vtkActor()
            self.building_actor.SetMapper(mapper)
            self.building_actor.GetProperty().SetPointSize(2)
            self.renderer.AddActor(self.building_actor)
            
        if ground:
            self.original_ground_polydata = dict_to_poly(ground)
            glyph = vtk.vtkVertexGlyphFilter()
            glyph.SetInputData(self.original_ground_polydata)
            glyph.Update()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(glyph.GetOutputPort())
            self.ground_actor = vtk.vtkActor()
            self.ground_actor.SetMapper(mapper)
            self.ground_actor.GetProperty().SetPointSize(2)
            self.renderer.AddActor(self.ground_actor)

        self.render_window.Render()
        self.renderer.ResetCamera()
        self.status_label.setText("✅ Point cloud rendered.")

    def _load_geojson_threaded(self, paths):
        self.status_label.setText("Reading GeoJSON outlines...")
        self.outline_geojsons = paths
        self.worker = GeoJsonLoaderWorker(paths)
        self.worker.finished.connect(self._on_geojson_loaded)
        self.worker.start()

    def _on_geojson_loaded(self, gdfs, msg):
        if not gdfs:
            self.status_label.setText(msg)
            return

        self.remove_building_outline()
        
        for gdf in gdfs:
            for idx, row in gdf.iterrows():
                geom = row.geometry
                if geom is None: continue

                fid = row.get("fid")
                dtm_z = row.get("DTM_mean", 0.0)
                if fid is not None: self.fid_dtm_map[str(fid)] = dtm_z

                polys = [geom] if isinstance(geom, Polygon) else list(geom.geoms) if isinstance(geom, MultiPolygon) else []
                
                for poly in polys:
                    exterior = poly.exterior.coords[:]
                    points = vtk.vtkPoints()
                    for x, y in exterior: points.InsertNextPoint(x, y, dtm_z)

                    lines = vtk.vtkCellArray()
                    for i in range(len(exterior) - 1):
                        line = vtk.vtkLine()
                        line.GetPointIds().SetId(0, i)
                        line.GetPointIds().SetId(1, i + 1)
                        lines.InsertNextCell(line)

                    polydata = vtk.vtkPolyData()
                    polydata.SetPoints(points)
                    polydata.SetLines(lines)

                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputData(polydata)
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)
                    actor.GetProperty().SetColor(1.0, 1.0, 0.0)
                    actor.GetProperty().SetLineWidth(2)
                    self.renderer.AddActor(actor)
                    self.outline_actors.append(actor)

        self.render_window.Render()
        self.status_label.setText("✅ Outlines loaded.")

    # ============================
    # Model Building (Main Thread)
    # ============================
    def _build_cityjson_models(self, cj):
        transform = cj.get("transform", {})
        scale = transform.get("scale", [1, 1, 1])
        translate = transform.get("translate", [0, 0, 0])

        raw_vertices = cj.get("vertices", [])
        vertices = [[v[0]*scale[0]+translate[0], v[1]*scale[1]+translate[1], v[2]*scale[2]+translate[2]] for v in raw_vertices]
        
        for obj_id, obj in cj.get("CityObjects", {}).items():
            actor = self.create_actor_from_cityobject(obj, vertices)
            if actor:
                self.models[obj_id] = actor
                self.cityjson_actors.append(actor)
                self.renderer.AddActor(actor)
                
        self.reset_view_top()

    def create_actor_from_cityobject(self, city_object, vertices):
        geometries = [g for g in city_object.get("geometry", []) if g.get("lod") == "2.2" and g.get("type") == "Solid"]
        if not geometries: return None

        points = vtk.vtkPoints()
        for v in vertices: points.InsertNextPoint(v)

        polys = vtk.vtkCellArray()
        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetName("Colors")

        for geom in geometries:
            semantics = geom.get("semantics", {})
            values = semantics.get("values", [])
            surfaces = semantics.get("surfaces", [])

            for shell_idx, shell in enumerate(geom.get("boundaries", [])):
                for face_idx, face in enumerate(shell):
                    if isinstance(face[0], list): face = [vid for ring in face for vid in ring]
                    polygon = vtk.vtkPolygon()
                    polygon.GetPointIds().SetNumberOfIds(len(face))
                    for i, vid in enumerate(face): polygon.GetPointIds().SetId(i, vid)
                    polys.InsertNextCell(polygon)

                    color = [255, 255, 255]
                    if values and shell_idx < len(values) and face_idx < len(values[shell_idx]):
                        idx = values[shell_idx][face_idx]
                        if isinstance(idx, list): idx = idx[0]
                        if idx is not None and 0 <= idx < len(surfaces):
                            stype = surfaces[idx].get("type", "")
                            if stype == "RoofSurface": color = [255, 0, 0]
                            elif stype == "WallSurface": color = [180, 180, 180]
                            elif stype == "GroundSurface": color = [100, 255, 100]
                    colors.InsertNextTuple3(*color)

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetPolys(polys)
        polydata.GetCellData().SetScalars(colors)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.SetScalarModeToUseCellData()
        mapper.ScalarVisibilityOn()

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().EdgeVisibilityOn()
        actor.GetProperty().SetLineWidth(0.5)
        return actor

    def read_obj_with_swizzle(self, filepath):
        self.remove_obj()
        with open(filepath, 'r') as f: lines = f.readlines()

        vertices = []
        building_groups = {}
        current_building = "default"

        for line in lines:
            if line.startswith('v '):
                parts = line.strip().split()
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith('g '):
                tokens = line.strip().split()
                current_building = tokens[1] if len(tokens) > 1 else "default"
                if current_building not in building_groups:
                    building_groups[current_building] = []
            elif line.startswith('f '):
                indices = [int(part.split('/')[0]) - 1 for part in line.strip().split()[1:]]
                if current_building not in building_groups:
                    building_groups[current_building] = []
                building_groups[current_building].append(indices)

        for building_id, faces in building_groups.items():
            dtm_offset = self.fid_dtm_map.get(str(building_id), 0.0)
            points = vtk.vtkPoints()
            polys = vtk.vtkCellArray()

            for x, y, z in vertices: points.InsertNextPoint(x, y, z + dtm_offset)
            for face in faces:
                if len(face) >= 3:
                    polygon = vtk.vtkPolygon()
                    polygon.GetPointIds().SetNumberOfIds(len(face))
                    for i, idx in enumerate(face): polygon.GetPointIds().SetId(i, idx)
                    polys.InsertNextCell(polygon)

            polydata = vtk.vtkPolyData()
            polydata.SetPoints(points)
            polydata.SetPolys(polys)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(polydata)
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(0.2, 0.6, 1.0)
            actor.GetProperty().EdgeVisibilityOn()
            actor.group_name = building_id
            self.renderer.AddActor(actor)
            self.obj_actors.append(actor)

        self.renderer.ResetCamera()
        self.render_window.Render()
        self.status_label.setText(f"✅ Loaded OBJ with {len(self.obj_actors)} groups.")

    # ============================
    # Removals
    # ============================
    def remove_cityjson(self):
        for actor in self.cityjson_actors: self.renderer.RemoveActor(actor)
        self.cityjson_actors.clear()
        self.models.clear()
        self.cityjson_data = None
        self.selected_actors.clear()
        self.render_window.Render()
        self.status_label.setText("CityJSON removed.")

    def remove_pointcloud(self):
        if self.building_actor: self.renderer.RemoveActor(self.building_actor); self.building_actor = None
        if self.ground_actor: self.renderer.RemoveActor(self.ground_actor); self.ground_actor = None
        self.original_building_polydata = None
        self.original_ground_polydata = None
        self.render_window.Render()
        self.status_label.setText("Point cloud removed.")

    def remove_building_outline(self):
        for actor in self.outline_actors: self.renderer.RemoveActor(actor)
        self.outline_actors.clear()
        self.render_window.Render()
        self.status_label.setText("Outlines removed.")

    def remove_obj(self):
        for actor in self.obj_actors: self.renderer.RemoveActor(actor)
        self.obj_actors.clear()
        self.render_window.Render()
        self.status_label.setText("OBJ removed.")

    # ============================
    # Slicing Box Widget
    # ============================
    def toggle_slicing_box(self):
        if not self.building_actor and not self.ground_actor:
            self.status_label.setText("No point cloud loaded to slice.")
            return

        if self.clipping_box_enabled:
            self.clipping_box_widget.Off()
            self.clipping_box_widget.SetInteractor(None)
            self.clipping_box_enabled = False
            self.clipping_box_widget = None
            self.status_label.setText("Slicing disabled.")
        else:
            if self.original_ground_polydata and not self.downsampled_ground_polydata:
                self.downsampled_ground_polydata = self.downsample_pointcloud(self.original_ground_polydata, 0.1)
            if self.original_building_polydata and not self.downsampled_building_polydata:
                self.downsampled_building_polydata = self.downsample_pointcloud(self.original_building_polydata, 0.1)

            if self.ground_actor and self.downsampled_ground_polydata:
                m = vtk.vtkPolyDataMapper(); m.SetInputData(self.downsampled_ground_polydata); self.ground_actor.SetMapper(m)
            if self.building_actor and self.downsampled_building_polydata:
                m = vtk.vtkPolyDataMapper(); m.SetInputData(self.downsampled_building_polydata); self.building_actor.SetMapper(m)

            self.enable_box_clipping()
            self.status_label.setText("Slicing enabled (using downsampled view).")

    def enable_box_clipping(self):
        box_widget = vtk.vtkBoxWidget()
        box_widget.SetInteractor(self.interactor)
        box_widget.SetPlaceFactor(1.0)
        
        poly_to_place = self.downsampled_building_polydata or self.downsampled_ground_polydata
        box_widget.SetInputData(poly_to_place)
        
        if self.last_clipping_bounds: box_widget.PlaceWidget(self.last_clipping_bounds)
        else: box_widget.PlaceWidget()

        box_widget.GetOutlineProperty().SetColor(1, 1, 0)
        box_widget.GetSelectedOutlineProperty().SetColor(1, 1, 0)
        box_widget.InsideOutOff()
        box_widget.On()
        self.clipping_box_widget = box_widget
        self.clipping_box_enabled = True

        def on_interaction(obj, event):
            planes = vtk.vtkPlanes()
            obj.GetPlanes(planes)
            self.last_clipping_planes = planes
            box_poly = vtk.vtkPolyData()
            obj.GetPolyData(box_poly)
            self.last_clipping_bounds = box_poly.GetBounds()

            for actor, poly in [(self.ground_actor, self.downsampled_ground_polydata), (self.building_actor, self.downsampled_building_polydata)]:
                if actor and poly:
                    clipper = vtk.vtkClipPolyData()
                    clipper.SetInputData(poly)
                    clipper.SetClipFunction(planes)
                    clipper.InsideOutOn()
                    clipper.Update()
                    m = vtk.vtkPolyDataMapper(); m.SetInputConnection(clipper.GetOutputPort())
                    actor.SetMapper(m)
            self.render_window.Render()
            
        box_widget.AddObserver("InteractionEvent", on_interaction)

    def restore_clipping_box(self):
        if not self.clipping_box_widget:
            self.enable_box_clipping()
            return
            
        poly_to_place = self.downsampled_building_polydata or self.downsampled_ground_polydata
        if poly_to_place:
            self.clipping_box_widget.SetInputData(poly_to_place)
            self.clipping_box_widget.PlaceWidget()

        if self.ground_actor and self.downsampled_ground_polydata:
            m = vtk.vtkPolyDataMapper(); m.SetInputData(self.downsampled_ground_polydata); self.ground_actor.SetMapper(m)
        if self.building_actor and self.downsampled_building_polydata:
            m = vtk.vtkPolyDataMapper(); m.SetInputData(self.downsampled_building_polydata); self.building_actor.SetMapper(m)
            
        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()
        self.last_clipping_planes = None
        self.last_clipping_bounds = None
        self.status_label.setText("Bounding box fully restored.")

    def downsample_pointcloud(self, polydata, ratio=0.01):
        n_points = polydata.GetNumberOfPoints()
        n_sample = max(1, int(n_points * ratio))
        ids = np.random.choice(n_points, size=n_sample, replace=False)
        
        points = vtk.vtkPoints()
        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetName("Colors")

        for i in ids:
            points.InsertNextPoint(*polydata.GetPoint(i))
            colors.InsertNextTuple3(*polydata.GetPointData().GetScalars().GetTuple3(i))

        out_poly = vtk.vtkPolyData()
        out_poly.SetPoints(points)
        out_poly.GetPointData().SetScalars(colors)
        glyph = vtk.vtkVertexGlyphFilter()
        glyph.SetInputData(out_poly)
        glyph.Update()
        return glyph.GetOutput()

    # ============================
    # Exporters
    # ============================
    def choose_export_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if d: self.export_dir = d; self.status_label.setText(f"Export dir: {d}")

    def export_selected_data(self):
        exported = []
        if self.cityjson_data:
            self.export_selection()
            exported.append("CityJSON & OBJ")
        if self.cityjson_data and self.outline_geojsons:
            self.export_selected_geojson()
            exported.append("Building Outline")
        if any(a in self.selected_actors for a in self.obj_actors):
            self.export_selected_obj()
            exported.append("OBJ + MTL")
            
        self.status_label.setText(f"✅ Exported: {', '.join(exported)}" if exported else "Nothing selected to export.")

    # (Original massive export_selection logic is kept completely intact and clean)
    def export_selection(self):
        if not self.cityjson_data: return
        selected_lod = self.lod_dropdown.currentText()
        vertices = self.cityjson_data.get("vertices", [])
        city_objects = self.cityjson_data.get("CityObjects", {})
        selected_ids = [obj_id for obj_id, actor in self.models.items() if actor in self.selected_actors]

        input_filename = self.cityjson_data.get("_input_filename", "export")
        base_name = os.path.splitext(os.path.basename(input_filename))[0]
        export_dir = self.export_dir if self.export_dir else os.getcwd()
        obj_filename = os.path.join(export_dir, f"{base_name}_selected.obj")
        obj_filename_unselected = os.path.join(export_dir, f"{base_name}_unselected.obj")
        cropped_filename = os.path.join(export_dir, f"{base_name}_cropped.json")

        transform = self.cityjson_data.get("transform", {})
        scale = transform.get("scale", [1, 1, 1])
        translate = transform.get("translate", [0, 0, 0])
        transformed_vertices = [[v[0]*scale[0]+translate[0], v[1]*scale[1]+translate[1], v[2]*scale[2]+translate[2]] for v in vertices]

        # Export OBJ Selected
        obj_lines = [f"v {v[0]} {v[1]} {v[2]}" for v in vertices]
        for obj_id in selected_ids:
            obj_lines.append(f"g {obj_id}")
            for geom in city_objects[obj_id].get("geometry", []):
                if geom.get("type") != "Solid" or geom.get("lod") != selected_lod: continue
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if isinstance(face[0], list): face = [vid for ring in face for vid in ring]
                        obj_lines.append(f"f {' '.join(str(vid + 1) for vid in face)}")
        with open(obj_filename, "w") as f: f.write("\n".join(obj_lines))

        # Export OBJ Unselected
        obj_lines_un = [f"v {v[0]} {v[1]} {v[2]}" for v in transformed_vertices]
        for obj_id, obj in city_objects.items():
            if obj_id in selected_ids: continue
            obj_lines_un.append(f"g {obj_id}")
            for geom in obj.get("geometry", []):
                if geom.get("type") != "Solid" or geom.get("lod") != "2.2": continue
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if isinstance(face[0], list): face = [vid for ring in face for vid in ring]
                        obj_lines_un.append(f"f {' '.join(str(vid + 1) for vid in face)}")
        with open(obj_filename_unselected, "w") as f: f.write("\n".join(obj_lines_un))

        # CityJSON export block logic
        filtered = {}
        for obj_id, obj in city_objects.items():
            if obj_id in selected_ids: continue
            filtered_geoms = [g for g in obj.get("geometry", []) if g.get("lod") == "2.2"]
            if filtered_geoms:
                new_obj = copy.deepcopy(obj)
                new_obj["geometry"] = filtered_geoms
                filtered[obj_id] = new_obj

        for obj_id, obj in city_objects.items():
            if obj_id not in filtered: continue
            for pid in obj.get("parents", []):
                if pid in city_objects and pid not in filtered:
                    filtered[pid] = copy.deepcopy(city_objects[pid])

        valid_ids = set(filtered.keys())
        for obj in filtered.values():
            if "parents" in obj: obj["parents"] = [p for p in obj["parents"] if p in valid_ids]
            if "children" in obj: obj["children"] = [c for c in obj["children"] if c in valid_ids]

        used = set()
        for obj in filtered.values():
            for geom in obj.get("geometry", []):
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if not face: continue
                        if isinstance(face[0], list): face = [vid for r in face for vid in r]
                        used.update(face)
                        
        used = sorted(used)
        index_map = {old: new for new, old in enumerate(used)}
        new_verts = [vertices[i] for i in used]

        for obj in filtered.values():
            for geom in obj.get("geometry", []):
                new_boundaries = []
                for shell in geom.get("boundaries", []):
                    new_shell = []
                    for face in shell:
                        if not face: new_shell.append(face); continue
                        if isinstance(face[0], list): new_shell.append([[index_map[v] for v in r] for r in face])
                        else: new_shell.append([index_map[v] for v in face])
                    new_boundaries.append(new_shell)
                geom["boundaries"] = new_boundaries

        cropped = OrderedDict([("type", "CityJSON"), ("version", "1.0")])
        if "transform" in self.cityjson_data: cropped["transform"] = self.cityjson_data["transform"]
        if "metadata" in self.cityjson_data:
            cropped["metadata"] = copy.deepcopy(self.cityjson_data["metadata"])
            ref = cropped["metadata"].get("referenceSystem", "")
            try:
                epsg = int(ref.split("/")[-1]) if "http" in ref else int(ref.split(":")[-1])
                cropped["metadata"]["referenceSystem"] = f"urn:ogc:def:crs:EPSG::{epsg}"
            except: cropped["metadata"]["referenceSystem"] = "urn:ogc:def:crs:EPSG::32749"
        cropped["CityObjects"] = filtered
        cropped["vertices"] = new_verts

        temp_fd, temp_path = tempfile.mkstemp(suffix="_v1.json")
        os.close(temp_fd)
        with open(temp_path, "w") as f: json.dump(cropped, f, indent=2)

        try:
            subprocess.run(["cjio", temp_path, "upgrade", "save", cropped_filename], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError: pass
        finally: os.remove(temp_path)

    def export_selected_obj(self):
        edir = self.export_dir if self.export_dir else os.getcwd()
        obj_path = os.path.join(edir, "exported_obj_selection.obj")
        mtl_path = os.path.join(edir, "exported_obj_selection.mtl")

        actors = [a for a in self.obj_actors if a in self.selected_actors]
        if not actors: return

        v_offset = 1
        obj_lines = ["mtllib exported_obj_selection.mtl"]
        mtl_lines = ["newmtl selected\nKd 1.0 1.0 0.0\n", "newmtl unselected\nKd 0.6 0.8 1.0\n"]

        for actor in self.obj_actors:
            mat = "selected" if actor in self.selected_actors else "unselected"
            obj_lines.extend([f"g {getattr(actor, 'group_name', 'group')}", f"usemtl {mat}"])
            
            pts = actor.GetMapper().GetInput().GetPoints()
            polys = actor.GetMapper().GetInput().GetPolys()
            
            for i in range(pts.GetNumberOfPoints()):
                x, y, z = pts.GetPoint(i)
                obj_lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
                
            id_list = vtk.vtkIdList()
            polys.InitTraversal()
            while polys.GetNextCell(id_list):
                obj_lines.append("f " + " ".join(str(id_list.GetId(j) + v_offset) for j in range(id_list.GetNumberOfIds())))
            v_offset += pts.GetNumberOfPoints()

        with open(obj_path, "w") as f: f.write("\n".join(obj_lines))
        with open(mtl_path, "w") as f: f.write("\n".join(mtl_lines))

    def export_selected_geojson(self):
        if not self.cityjson_data or not self.outline_geojsons: return
        s_ids = [k for k, a in self.models.items() if a in self.selected_actors]
        if not s_ids: return

        centroids = self.calculate_centroids(s_ids)
        edir = self.export_dir if self.export_dir else os.getcwd()
        
        for path in self.outline_geojsons:
            gdf = gpd.read_file(path)
            selected = [r for idx, r in gdf.iterrows() if r.geometry and any(r.geometry.contains(c) for c in centroids)]
            
            if selected:
                new_gdf = gpd.GeoDataFrame(selected, columns=gdf.columns, crs=gdf.crs)
                base = os.path.splitext(os.path.basename(path))[0]
                new_gdf.to_file(os.path.join(edir, f"{base}_selected.geojson"), driver="GeoJSON")
                new_gdf.to_crs(epsg=4326).to_file(os.path.join(edir, f"{base}_selected_wgs84.geojson"), driver="GeoJSON")

    def calculate_centroids(self, s_ids):
        centroids = []
        verts = self.cityjson_data.get("vertices", [])
        sc = self.cityjson_data.get("transform", {}).get("scale", [1,1,1])
        tr = self.cityjson_data.get("transform", {}).get("translate", [0,0,0])

        for obj_id in s_ids:
            obj = self.cityjson_data.get("CityObjects", {}).get(obj_id)
            if not obj: continue
            coords = []
            for geom in obj.get("geometry", []):
                if geom.get("type") != "Solid": continue
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if isinstance(face[0], list): face = [v for r in face for v in r]
                        for vid in face:
                            if isinstance(vid, int) and 0 <= vid < len(verts):
                                v = verts[vid]
                                coords.append([v[0]*sc[0]+tr[0], v[1]*sc[1]+tr[1], v[2]*sc[2]+tr[2]])
            if coords:
                c = np.mean(np.array(coords), axis=0)
                centroids.append(Point(c[0], c[1]))
        return centroids

    def closeEvent(self, event):
        if self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Finalize()
            self.vtk_widget.GetRenderWindow().ReleaseGraphicsResources()
            self.vtk_widget.Finalize()
            self.vtk_widget.deleteLater()
            self.vtk_widget = None
        super().closeEvent(event)