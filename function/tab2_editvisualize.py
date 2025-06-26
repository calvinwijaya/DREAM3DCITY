import sys
import os
import json
import shutil
import vtk
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QPushButton, QLabel, QFileDialog, QSizePolicy, QApplication, QComboBox, QCheckBox, QGroupBox
from PyQt5.QtCore import Qt, QTimer
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import geopandas as gpd
from collections import OrderedDict
import laspy
import numpy as np
import tempfile
import subprocess
import copy

class VisualizeTab(QWidget):
    def __init__(self, folder=None, cityjson_file=None):
        super().__init__()
        self.models = {}
        self.selected_actors = set()
        self.cityjson_data = None
        self.outline_geojsons = []
        self.cityjson_actors = []
        self.outline_actors = []

        self.obj_actor = None
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

        # Store fid and dtm_mean from bo for obj
        self.fid_dtm_map = {}

        main_layout = QHBoxLayout(self)

        # Left panel: buttons + status
        left_panel = QVBoxLayout()
        self.load_button = QPushButton("Load CityJSON")
        self.load_button.clicked.connect(self.load_cityjson_file_dialog)

        self.load_pointcloud_button = QPushButton("Load Point Cloud")
        self.load_pointcloud_button.clicked.connect(self.load_pointcloud_file_dialog)
        
        self.load_outline_button = QPushButton("Load Building Outline")
        self.load_outline_button.clicked.connect(self.load_building_outline_geojson)

        self.load_obj_button = QPushButton("Load OBJ ")
        self.load_obj_button.clicked.connect(self.load_obj_file_dialog)

        # === 1. Load Data ===
        load_group = QGroupBox("Load Data")
        load_layout = QVBoxLayout()
        load_layout.addWidget(self.load_button)
        load_layout.addWidget(self.load_pointcloud_button)
        load_layout.addWidget(self.load_outline_button)
        load_layout.addWidget(self.load_obj_button)
        load_group.setLayout(load_layout)
        left_panel.addWidget(load_group)
        load_group.setStyleSheet("QGroupBox { font-weight: bold; }")

        self.export_dir = ""

        self.choose_dir_button = QPushButton("Choose Export Directory")
        self.choose_dir_button.clicked.connect(self.choose_export_directory)
        
        self.lod_dropdown = QComboBox()
        self.lod_dropdown.addItems(["1.2", "1.3", "2.2"])

        self.export_button = QPushButton("Export Selected Data")
        self.export_button.clicked.connect(self.export_selected_data)

        # === 2. Export Data ===
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()
        export_layout.addWidget(self.choose_dir_button)
        export_layout.addWidget(QLabel("OBJ Export LOD:"))
        export_layout.addWidget(self.lod_dropdown)
        export_layout.addWidget(self.export_button)
        export_group.setLayout(export_layout)
        left_panel.addWidget(export_group)
        export_group.setStyleSheet("QGroupBox { font-weight: bold; }")

        self.status_label = QLabel("No CityJSON file loaded")
        self.status_label.setWordWrap(True)
        left_panel.addWidget(self.status_label)

        left_panel.addStretch()  # push everything to top

        self.slicing_button = QPushButton("Toggle Slicing Widgets")
        self.slicing_button.clicked.connect(self.toggle_slicing_box)

        self.restore_box_button = QPushButton("Restore Bounding Box")
        self.restore_box_button.clicked.connect(self.restore_clipping_box)

        # === 3. Visualization Controls ===
        viz_group = QGroupBox("Visualization")
        viz_layout = QVBoxLayout()
        viz_layout.addWidget(self.slicing_button)
        viz_layout.addWidget(self.restore_box_button)
        viz_group.setLayout(viz_layout)
        left_panel.addWidget(viz_group)
        viz_group.setStyleSheet("QGroupBox { font-weight: bold; }")

        self.remove_cityjson_button = QPushButton("Remove CityJSON")
        self.remove_cityjson_button.clicked.connect(self.remove_cityjson)

        self.remove_pointcloud_button = QPushButton("Remove Point Cloud")
        self.remove_pointcloud_button.clicked.connect(self.remove_pointcloud)

        self.remove_outline_button = QPushButton("Remove Building Outline")
        self.remove_outline_button.clicked.connect(self.remove_building_outline)

        self.remove_obj_button = QPushButton("Remove OBJ")
        self.remove_obj_button.clicked.connect(self.remove_obj)

        # === 4. Remove Data ===
        remove_group = QGroupBox("Remove Data")
        remove_layout = QVBoxLayout()
        remove_layout.addWidget(self.remove_cityjson_button)
        remove_layout.addWidget(self.remove_pointcloud_button)
        remove_layout.addWidget(self.remove_outline_button)
        remove_layout.addWidget(self.remove_obj_button)
        remove_group.setLayout(remove_layout)
        left_panel.addWidget(remove_group)
        remove_group.setStyleSheet("QGroupBox { font-weight: bold; }")

        # Right panel: VTK widget
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.vtk_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Overlay widget container
        self.overlay_widget = QWidget(self.vtk_widget)
        self.overlay_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.overlay_widget.setStyleSheet("background-color: rgb(255, 255, 255); border-radius: 4px;")
        self.overlay_widget.setFixedSize(200, 180)

        overlay_layout = QVBoxLayout(self.overlay_widget)
        overlay_layout.setContentsMargins(5, 5, 5, 5)

        # Add toggle button
        self.toggle_overlay_button = QPushButton("▶ Show Layers")
        self.toggle_overlay_button.setFlat(True)
        self.toggle_overlay_button.clicked.connect(self.toggle_layer_visibility)
        overlay_layout.addWidget(self.toggle_overlay_button)

        # Create collapsible content widget
        self.overlay_content = QWidget()
        overlay_content_layout = QVBoxLayout(self.overlay_content)
        overlay_content_layout.setContentsMargins(0, 0, 0, 0)

        self.cityjson_checkbox = QCheckBox("Show CityJSON")
        self.cityjson_checkbox.setChecked(True)
        self.cityjson_checkbox.stateChanged.connect(self.toggle_cityjson_visibility)
        overlay_content_layout .addWidget(self.cityjson_checkbox)

        self.building_checkbox = QCheckBox("Show Building Points")
        self.building_checkbox.setChecked(True)
        self.building_checkbox.stateChanged.connect(self.toggle_building_points)
        overlay_content_layout .addWidget(self.building_checkbox)

        self.ground_checkbox = QCheckBox("Show Ground Points")
        self.ground_checkbox.setChecked(True)
        self.ground_checkbox.stateChanged.connect(self.toggle_ground_points)
        overlay_content_layout .addWidget(self.ground_checkbox)

        self.outline_checkbox = QCheckBox("Show Building Outline")
        self.outline_checkbox.setChecked(True)
        self.outline_checkbox.stateChanged.connect(self.toggle_outline_visibility)
        overlay_content_layout .addWidget(self.outline_checkbox)

        self.obj_checkbox = QCheckBox("Show OBJ")
        self.obj_checkbox.setChecked(True)
        self.obj_checkbox.stateChanged.connect(self.toggle_obj_visibility)
        overlay_content_layout .addWidget(self.obj_checkbox)

        # Initially hidden
        self.overlay_content.setVisible(True)
        overlay_layout.addWidget(self.overlay_content)
        self.overlay_widget.move(self.vtk_widget.width() - 210, 10)

        # For View Controls
        self.view_overlay_widget = QWidget(self.vtk_widget)
        self.view_overlay_widget.setStyleSheet("background-color: rgb(255, 255, 255); border-radius: 4px;")
        self.view_overlay_widget.setFixedSize(140, 210)

        view_layout = QVBoxLayout(self.view_overlay_widget)
        view_layout.setContentsMargins(5, 5, 5, 5)

        self.toggle_view_button = QPushButton("▶ View Controls")
        self.toggle_view_button.setFlat(True)
        self.toggle_view_button.clicked.connect(self.toggle_view_visibility)
        view_layout.addWidget(self.toggle_view_button)

        self.view_content = QWidget()
        view_content_layout = QVBoxLayout(self.view_content)
        view_content_layout.setContentsMargins(0, 0, 0, 0)

        btn_top = QPushButton("Top View")
        btn_top.clicked.connect(self.reset_view_top)
        btn_top.setStyleSheet(self.view_button_style())
        view_content_layout.addWidget(btn_top)

        btn_bottom = QPushButton("Bottom View")
        btn_bottom.clicked.connect(self.reset_view_bottom)
        btn_bottom.setStyleSheet(self.view_button_style())
        view_content_layout.addWidget(btn_bottom)

        btn_front = QPushButton("Front View")
        btn_front.clicked.connect(self.reset_view_front)
        btn_front.setStyleSheet(self.view_button_style())
        view_content_layout.addWidget(btn_front)

        btn_back = QPushButton("Back View")
        btn_back.clicked.connect(self.reset_view_back)
        btn_back.setStyleSheet(self.view_button_style())
        view_content_layout.addWidget(btn_back)

        btn_left = QPushButton("Left View")
        btn_left.clicked.connect(self.reset_view_left)
        btn_left.setStyleSheet(self.view_button_style())
        view_content_layout.addWidget(btn_left)

        btn_right = QPushButton("Right View")
        btn_right.clicked.connect(self.reset_view_right)
        btn_right.setStyleSheet(self.view_button_style())
        view_content_layout.addWidget(btn_right)

        self.view_content.setVisible(False)
        self.toggle_view_button.setText("▶ View Controls")
        self.view_overlay_widget.setFixedHeight(30)
        view_layout.addWidget(self.view_content)

        self.view_overlay_widget.move(10, 10)

        main_layout.addLayout(left_panel, 1)
        main_layout.addWidget(self.vtk_widget, 4)

        # VTK renderer setup
        self.renderer = vtk.vtkRenderer()
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
        style.OnLeftButtonDown = lambda obj, evt: None  # Disable rotation
        self.interactor.SetInteractorStyle(style)

        if cityjson_file:
            self.load_cityjson(cityjson_file)
            self.load_models(cityjson_file)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 10
        if self.vtk_widget:
            if self.overlay_widget:
                self.overlay_widget.move(self.vtk_widget.width() - self.overlay_widget.width() - margin, margin)
            if self.view_overlay_widget:
                self.view_overlay_widget.move(margin, margin)

    def toggle_layer_visibility(self):
        expanded = self.overlay_content.isVisible()
        self.overlay_content.setVisible(not expanded)
        self.toggle_overlay_button.setText("▼ Hide Layers" if not expanded else "▶ Show Layers")
        self.overlay_widget.setFixedHeight(180 if not expanded else 30)

    def toggle_view_visibility(self):
        expanded = self.view_content.isVisible()
        self.view_content.setVisible(not expanded)
        self.toggle_view_button.setText("▼ Hide Views" if not expanded else "▶ View Controls")
        self.view_overlay_widget.setFixedHeight(290 if not expanded else 30)

    def view_button_style(self):
        return """
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            padding: 6px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #d0eaff;
            border: 1px solid #007acc;
        }
        QPushButton:pressed {
            background-color: #a5d3ff;
        }
        """

    def on_mouse_click(self, obj, event):
        click_pos = self.interactor.GetEventPosition()
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        actor = self.picker.GetActor()

        # Exclude point cloud actors
        excluded = [self.ground_actor, self.building_actor]

        if actor and actor not in excluded:
            if actor in self.selected_actors:
                # ✅ Deselect it
                actor.GetMapper().ScalarVisibilityOn()
                actor.GetProperty().SetColor(0.2, 0.6, 1.0)  # Reset to original color
                self.selected_actors.remove(actor)
            else:
                # ✅ Select it
                actor.GetMapper().ScalarVisibilityOff()
                actor.GetProperty().SetColor(1.0, 1.0, 0.0)  # Yellow
                self.selected_actors.add(actor)

            self.renderer.ResetCameraClippingRange()
            self.render_window.Render()
    
    def set_camera_view(self, position, view_up):
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(*position)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(*view_up)
        self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()

    def reset_view_top(self):
        self.set_camera_view((0, 0, 1), (0, 1, 0))

    def reset_view_bottom(self):
        self.set_camera_view((0, 0, -1), (0, -1, 0))

    def reset_view_front(self):
        self.set_camera_view((0, -1, 0), (0, 0, 1))

    def reset_view_back(self):
        self.set_camera_view((0, 1, 0), (0, 0, 1))

    def reset_view_left(self):
        self.set_camera_view((-1, 0, 0), (0, 0, 1))

    def reset_view_right(self):
        self.set_camera_view((1, 0, 0), (0, 0, 1))

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
    
    def toggle_cityjson_visibility(self, state):
        visible = state == Qt.Checked
        for actor in self.cityjson_actors:
            actor.SetVisibility(visible)
        self.render_window.Render()

    def toggle_building_points(self, state):
        if hasattr(self, 'building_actor') and self.building_actor:
            self.building_actor.SetVisibility(state == Qt.Checked)
            self.render_window.Render()

    def toggle_ground_points(self, state):
        if hasattr(self, 'ground_actor') and self.ground_actor:
            self.ground_actor.SetVisibility(state == Qt.Checked)
            self.render_window.Render()

    def toggle_outline_visibility(self, state):
        visible = state == Qt.Checked
        for actor in self.outline_actors:
            actor.SetVisibility(visible)
        self.render_window.Render()

    def toggle_obj_visibility(self, state):
        visible = state == Qt.Checked
        for actor in getattr(self, 'obj_actors', []):
            actor.SetVisibility(visible)
        self.render_window.Render()

    def remove_cityjson(self):
        for actor in self.cityjson_actors:
            self.renderer.RemoveActor(actor)
        self.cityjson_actors.clear()
        self.models.clear()
        self.cityjson_data = None
        self.selected_actors.clear()
        self.render_window.Render()
        self.status_label.setText("CityJSON removed.")

    def remove_pointcloud(self):
        if hasattr(self, 'building_actor') and self.building_actor:
            self.renderer.RemoveActor(self.building_actor)
            self.building_actor = None
        if hasattr(self, 'ground_actor') and self.ground_actor:
            self.renderer.RemoveActor(self.ground_actor)
            self.ground_actor = None
        self.render_window.Render()
        self.status_label.setText("Point cloud removed.")
    
    def remove_building_outline(self):
        for actor in self.outline_actors:
            self.renderer.RemoveActor(actor)
        self.outline_actors.clear()
        self.render_window.Render()
        self.status_label.setText("Building outlines removed.")

    def remove_obj(self):
        if hasattr(self, 'obj_actors') and self.obj_actors:
            for actor in self.obj_actors:
                self.renderer.RemoveActor(actor)
            self.obj_actors = []
            self.render_window.Render()
            self.status_label.setText("OBJ models removed.")
        else:
            self.status_label.setText("No OBJ actors to remove.")
    
    def load_cityjson_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CityJSON File", "", "CityJSON Files (*.json *.city.json)")
        if file_path:
            self.status_label.setText(f"Loading file:\n{file_path}")
            self.cityjson_data = None
            self.renderer.RemoveAllViewProps()
            self.models.clear()
            self.load_cityjson(file_path)
            self.load_models(file_path)
            self.status_label.setText(f"CityJSON file loaded at:\n{file_path}")

    def load_cityjson(self, file_path):
        with open(file_path, 'r') as f:
            self.cityjson_data = json.load(f)
            self.cityjson_data["_input_filename"] = file_path
        self.export_dir = "" 

    def load_models(self, cityjson_file):
        with open(cityjson_file, 'r') as f:
            cj = json.load(f)

        # Get transform (if exists)
        transform = cj.get("transform", {})
        scale = transform.get("scale", [1, 1, 1])
        translate = transform.get("translate", [0, 0, 0])

        # Apply transformation to vertices
        raw_vertices = cj.get("vertices", [])
        vertices = [
            [
                v[0] * scale[0] + translate[0],
                v[1] * scale[1] + translate[1],
                v[2] * scale[2] + translate[2]
            ]
            for v in raw_vertices
        ]
        city_objects = cj.get("CityObjects", {})

        for obj_id, obj in city_objects.items():
            actor = self.create_actor_from_cityobject(obj, vertices)
            if actor:
                self.models[obj_id] = actor
                self.cityjson_actors.append(actor)
                self.renderer.AddActor(actor)
        self.reset_view_top()

    def create_actor_from_cityobject(self, city_object, vertices):
        geometries = [g for g in city_object.get("geometry", []) if g.get("lod") == "2.2" and g.get("type") == "Solid"]
        if not geometries:
            return None

        points = vtk.vtkPoints()
        for v in vertices:
            points.InsertNextPoint(v)

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
                    if isinstance(face[0], list):
                        face = [vid for ring in face for vid in ring]

                    polygon = vtk.vtkPolygon()
                    polygon.GetPointIds().SetNumberOfIds(len(face))
                    for i, vid in enumerate(face):
                        polygon.GetPointIds().SetId(i, vid)
                    polys.InsertNextCell(polygon)

                    color = [255, 255, 255]
                    if values and shell_idx < len(values) and face_idx < len(values[shell_idx]):
                        idx = values[shell_idx][face_idx]
                        if isinstance(idx, list):
                            idx = idx[0]
                        if idx is not None and 0 <= idx < len(surfaces):
                            surf_type = surfaces[idx].get("type", "")
                            if surf_type == "RoofSurface":
                                color = [255, 0, 0]
                            elif surf_type == "WallSurface":
                                color = [180, 180, 180]
                            elif surf_type == "GroundSurface":
                                color = [100, 255, 100]
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

    def export_selected_data(self):
        exported = []

        if self.cityjson_data:
            self.export_selection()  # Reuse full CityJSON export function
            exported.append("CityJSON & OBJ")

        if self.cityjson_data and self.outline_geojsons:
            self.export_selected_geojson()  # Reuse BO export
            exported.append("Building Outline")

        selected_obj_actors = [
            actor for actor in getattr(self, 'obj_actors', []) if actor in self.selected_actors
        ]
        if selected_obj_actors:
            self.export_selected_obj()
            exported.append("OBJ with MTL")

        if exported:
            self.status_label.setText(f"Exported: {', '.join(exported)}")
        else:
            self.status_label.setText("No CityJSON, OBJ, or outlines selected.")

    def export_selection(self):
        if not self.cityjson_data:
            return

        selected_lod = self.lod_dropdown.currentText()
        vertices = self.cityjson_data.get("vertices", [])
        city_objects = self.cityjson_data.get("CityObjects", {})
        selected_ids = [obj_id for obj_id, actor in self.models.items() if actor in self.selected_actors]

        # File paths
        input_filename = self.cityjson_data.get("_input_filename", "export")
        base_name = os.path.splitext(os.path.basename(input_filename))[0]
        export_dir = self.export_dir if self.export_dir else os.getcwd()
        obj_filename = os.path.join(export_dir, f"{base_name}_selected.obj")
        obj_filename_unselected = os.path.join(export_dir, f"{base_name}_unselected.obj")
        cropped_filename = os.path.join(export_dir, f"{base_name}_cropped.json")

        # Store UTM reference
        transform = self.cityjson_data.get("transform", {})
        scale = transform.get("scale", [1, 1, 1])
        translate = transform.get("translate", [0, 0, 0])

        transformed_vertices = [
            [
                v[0] * scale[0] + translate[0],
                v[1] * scale[1] + translate[1],
                v[2] * scale[2] + translate[2]
            ]
            for v in vertices
        ]

        # Export OBJ Selected
        obj_lines = [f"v {v[0]} {v[1]} {v[2]}" for v in vertices]
        for obj_id in selected_ids:
            obj = city_objects[obj_id]
            obj_lines.append(f"g {obj_id}")
            for geom in obj.get("geometry", []):
                if geom.get("type") != "Solid" or geom.get("lod") != selected_lod:
                    continue
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if isinstance(face[0], list):
                            face = [vid for ring in face for vid in ring]
                        face_indices = [f"{vid + 1}" for vid in face]
                        obj_lines.append(f"f {' '.join(face_indices)}")

        with open(obj_filename, "w") as f:
            f.write("\n".join(obj_lines))

        # Export OBJ Not Selected      
        obj_lines_unselected = [f"v {v[0]} {v[1]} {v[2]}" for v in transformed_vertices]
        for obj_id in city_objects:
            if obj_id not in selected_ids:
                obj = city_objects[obj_id]
                obj_lines_unselected.append(f"g {obj_id}")
                for geom in obj.get("geometry", []):
                    if geom.get("type") != "Solid" or geom.get("lod") != "2.2":
                        continue
                    for shell in geom.get("boundaries", []):
                        for face in shell:
                            if isinstance(face[0], list):
                                face = [vid for ring in face for vid in ring]
                            face_indices = [f"{vid + 1}" for vid in face]
                            obj_lines_unselected.append(f"f {' '.join(face_indices)}")

        with open(obj_filename_unselected, "w") as f:
            f.write("\n".join(obj_lines_unselected))

        # Filter non-selected CityObjects with LOD 2.2
        filtered_city_objects = {}
        for obj_id, obj in city_objects.items():
            if obj_id in selected_ids:
                continue
            filtered_geoms = [g for g in obj.get("geometry", []) if g.get("lod") == "2.2"]
            if filtered_geoms:
                new_obj = copy.deepcopy(obj)
                new_obj["geometry"] = filtered_geoms
                filtered_city_objects[obj_id] = new_obj

        # Add parents if necessary
        for obj_id, obj in city_objects.items():
            if obj_id not in filtered_city_objects:
                continue
            if "parents" in obj:
                for pid in obj["parents"]:
                    if pid in city_objects and pid not in filtered_city_objects:
                        filtered_city_objects[pid] = copy.deepcopy(city_objects[pid])

        # Clean up parents/children
        valid_ids = set(filtered_city_objects.keys())
        for obj in filtered_city_objects.values():
            if "parents" in obj:
                obj["parents"] = [p for p in obj["parents"] if p in valid_ids]
            if "children" in obj:
                obj["children"] = [c for c in obj["children"] if c in valid_ids]

        # Collect used vertices
        used_indices = set()
        for obj in filtered_city_objects.values():
            for geom in obj.get("geometry", []):
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if not face:
                            continue
                        if isinstance(face[0], list):  # Multi-ring
                            face = [vid for ring in face for vid in ring]
                        used_indices.update(face)

        used_indices = sorted(used_indices)
        index_map = {old: new for new, old in enumerate(used_indices)}
        new_vertices = [vertices[i] for i in used_indices]

        # Remap geometry indices
        for obj in filtered_city_objects.values():
            for geom in obj.get("geometry", []):
                new_boundaries = []
                for shell in geom.get("boundaries", []):
                    new_shell = []
                    for face in shell:
                        if not face:
                            new_shell.append(face)
                            continue
                        if isinstance(face[0], list):
                            new_face = [[index_map[vid] for vid in ring] for ring in face]
                        else:
                            new_face = [index_map[vid] for vid in face]
                        new_shell.append(new_face)
                    new_boundaries.append(new_shell)
                geom["boundaries"] = new_boundaries

        # Assemble v1.0 CityJSON
        cropped_cityjson = OrderedDict()
        cropped_cityjson["type"] = "CityJSON"
        cropped_cityjson["version"] = "1.0"
        if "transform" in self.cityjson_data:
            cropped_cityjson["transform"] = self.cityjson_data["transform"]
        if "metadata" in self.cityjson_data:
            cropped_cityjson["metadata"] = copy.deepcopy(self.cityjson_data["metadata"])
            ref = cropped_cityjson["metadata"].get("referenceSystem", "")
            if "EPSG" in ref:
                try:
                    epsg = int(ref.split("/")[-1]) if "http" in ref else int(ref.split(":")[-1])
                    cropped_cityjson["metadata"]["referenceSystem"] = f"urn:ogc:def:crs:EPSG::{epsg}"
                except:
                    cropped_cityjson["metadata"]["referenceSystem"] = "urn:ogc:def:crs:EPSG::32749"  # fallback
        cropped_cityjson["CityObjects"] = filtered_city_objects
        cropped_cityjson["vertices"] = new_vertices

        # Save temporary v1.0 and upgrade using cjio
        temp_v1_fd, temp_v1_path = tempfile.mkstemp(suffix="_v1.json")
        os.close(temp_v1_fd)
        with open(temp_v1_path, "w") as f:
            json.dump(cropped_cityjson, f, indent=2)

        cmd = ["cjio", temp_v1_path, "upgrade", "save", cropped_filename]
        try:
            result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(result.stdout)
            print(f"✅ Saved (v2.0): {cropped_filename}")
        except subprocess.CalledProcessError as e:
            print("❌ cjio error:", e.stderr)
            self.status_label.setText("CJIO upgrade failed.")
            return
        finally:
            os.remove(temp_v1_path)

        self.status_label.setText(f"Exported:\n - {obj_filename}\n - {cropped_filename}")

    def export_selected_obj(self):
        export_dir = self.export_dir if self.export_dir else os.getcwd()
        obj_path = os.path.join(export_dir, "exported_obj_selection.obj")
        mtl_path = os.path.join(export_dir, "exported_obj_selection.mtl")

        all_obj_actors = getattr(self, 'obj_actors', [])
        if not all_obj_actors:
            self.status_label.setText("No OBJ actors to export.")
            return

        vertex_offset = 1
        obj_lines = ["mtllib exported_obj_selection.mtl"]
        mtl_lines = [
            "newmtl selected",
            "Kd 1.0 1.0 0.0",  # Yellow for selected
            "newmtl unselected",
            "Kd 0.6 0.8 1.0",  # Blue/gray for unselected
        ]

        for idx, actor in enumerate(all_obj_actors):
            is_selected = actor in self.selected_actors
            mat_name = "selected" if is_selected else "unselected"
            group_name = getattr(actor, "group_name", f"group_{idx}")

            polydata = actor.GetMapper().GetInput()
            points = polydata.GetPoints()
            polys = polydata.GetPolys()

            # OBJ Group
            obj_lines.append(f"g {group_name}")
            obj_lines.append(f"usemtl {mat_name}")

            # Write vertices
            for i in range(points.GetNumberOfPoints()):
                x, y, z = points.GetPoint(i)
                obj_lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")

            # Write faces
            id_list = vtk.vtkIdList()
            polys.InitTraversal()
            while polys.GetNextCell(id_list):
                face = [str(id_list.GetId(j) + vertex_offset) for j in range(id_list.GetNumberOfIds())]
                obj_lines.append("f " + " ".join(face))

            vertex_offset += points.GetNumberOfPoints()

        with open(obj_path, "w") as obj_file:
            obj_file.write("\n".join(obj_lines))
        with open(mtl_path, "w") as mtl_file:
            mtl_file.write("\n".join(mtl_lines))

        self.status_label.setText(f"✅ Exported all OBJ (selected = yellow) to:\n - {obj_path}\n - {mtl_path}")

    def choose_export_directory(self):
            dir_path = QFileDialog.getExistingDirectory(self, "Select Export Directory")
            if dir_path:
                self.export_dir = dir_path
                self.status_label.setText(f"Export directory set to:\n{dir_path}")
        
    def load_building_outline_geojson(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Building Outline GeoJSON Files", "", "GeoJSON Files (*.geojson *.json)")
        if files:
            self.outline_geojsons = files
            self.status_label.setText(f"Loaded {len(files)} GeoJSON outline file(s).")
            self.visualize_building_outline(files)           

    def export_selected_geojson(self):
        if not self.cityjson_data or not self.outline_geojsons:
            self.status_label.setText("Load CityJSON and GeoJSON files first.")
            return

        selected_ids = [obj_id for obj_id, actor in self.models.items() if actor in self.selected_actors]
        if not selected_ids:
            self.status_label.setText("No selected buildings.")
            return

        # Calculate centroids of selected buildings
        building_centroids = self.calculate_centroids(selected_ids)

        export_dir = self.export_dir if self.export_dir else os.getcwd()
        exported_files = []

        for path in self.outline_geojsons:
            gdf = gpd.read_file(path)
            selected_polygons = []

            for idx, row in gdf.iterrows():
                poly = row.geometry
                if poly is None:
                    continue
                for centroid in building_centroids:
                    if poly.contains(centroid):
                        selected_polygons.append(row)
                        break  # Only need one match to keep the polygon

            if selected_polygons:
                new_gdf = gpd.GeoDataFrame(selected_polygons, columns=gdf.columns, crs=gdf.crs)
                basename = os.path.splitext(os.path.basename(path))[0]

                # Export in original CRS
                out_path = os.path.join(export_dir, f"{basename}_selected.geojson")
                new_gdf.to_file(out_path, driver="GeoJSON")
                exported_files.append(out_path)

                # Reproject to WGS84 (EPSG:4326) and export
                new_gdf_wgs84 = new_gdf.to_crs(epsg=4326)
                out_path_wgs84 = os.path.join(export_dir, f"{basename}_selected_wgs84.geojson")
                new_gdf_wgs84.to_file(out_path_wgs84, driver="GeoJSON")
                exported_files.append(out_path_wgs84)

        if exported_files:
            self.status_label.setText(f"Exported selected polygons to:\n" + "\n".join(exported_files))
        else:
            self.status_label.setText("No centroids matched with outline polygons.")

    def calculate_centroids(self, selected_ids):
        from numpy import array, mean
        from shapely.geometry import Point

        centroids = []
        vertices = self.cityjson_data.get("vertices", [])
        transform = self.cityjson_data.get("transform", {})
        scale = transform.get("scale", [1.0, 1.0, 1.0])
        translate = transform.get("translate", [0.0, 0.0, 0.0])
        city_objects = self.cityjson_data.get("CityObjects", {})

        def apply_transform(v):
            return [
                v[0] * scale[0] + translate[0],
                v[1] * scale[1] + translate[1],
                v[2] * scale[2] + translate[2]
            ]

        for obj_id in selected_ids:
            obj = city_objects.get(obj_id)
            if not obj:
                continue
            all_coords = []
            for geom in obj.get("geometry", []):
                if geom.get("type") != "Solid":
                    continue
                for shell in geom.get("boundaries", []):
                    for face in shell:
                        if isinstance(face[0], list):  # multi-ring face
                            face = [vid for ring in face for vid in ring]
                        for vid in face:
                            if isinstance(vid, int) and 0 <= vid < len(vertices):
                                v = vertices[vid]
                                v_transformed = apply_transform(v)
                                all_coords.append(v_transformed)
            if all_coords:
                centroid_coords = mean(array(all_coords), axis=0)
                centroids.append(Point(centroid_coords[0], centroid_coords[1]))

        return centroids

    def load_pointcloud_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open LAS File", "", "LAS Files (*.las)")
        if file_path:
            self.load_pointcloud(file_path)
            self.status_label.setText(f"Point cloud loaded from:\n{file_path}")

    def load_pointcloud(self, file_path):
        las = laspy.read(file_path)

        ground_mask = las.classification == 2
        building_mask = las.classification == 6

        if not np.any(ground_mask) and not np.any(building_mask):
            self.status_label.setText("No ground (2) or building (6) points found.")
            return

        self.remove_pointcloud()

        def create_polydata(mask):
            x, y, z = las.x[mask], las.y[mask], las.z[mask]
            red, green, blue = las.red[mask], las.green[mask], las.blue[mask]

            # Normalize RGB if needed
            if np.max([red.max(), green.max(), blue.max()]) > 255:
                red = (red / 256).astype(np.uint8)
                green = (green / 256).astype(np.uint8)
                blue = (blue / 256).astype(np.uint8)

            points = vtk.vtkPoints()
            colors = vtk.vtkUnsignedCharArray()
            colors.SetNumberOfComponents(3)
            colors.SetName("Colors")

            for i in range(len(x)):
                points.InsertNextPoint(x[i], y[i], z[i])
                colors.InsertNextTuple3(red[i], green[i], blue[i])

            polydata = vtk.vtkPolyData()
            polydata.SetPoints(points)
            polydata.GetPointData().SetScalars(colors)

            return polydata

        if np.any(building_mask):
            self.original_building_polydata = create_polydata(building_mask)
            glyph = vtk.vtkVertexGlyphFilter()
            glyph.SetInputData(self.original_building_polydata)
            glyph.Update()

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(glyph.GetOutputPort())

            self.building_actor = vtk.vtkActor()
            self.building_actor.SetMapper(mapper)
            self.building_actor.GetProperty().SetPointSize(2)

            self.renderer.AddActor(self.building_actor)

        if np.any(ground_mask):
            self.original_ground_polydata = create_polydata(ground_mask)
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
        self.status_label.setText("Loaded ground and/or building points.")

    def visualize_building_outline(self, geojson_paths):
        for path in geojson_paths:
            gdf = gpd.read_file(path)

            # If using no elevation:
            # for geom in gdf.geometry:
            #     if geom is None:
            #         continue

            for idx, row in gdf.iterrows():
                geom = row.geometry
                if geom is None:
                    continue

                fid = row.get("fid")
                dtm_z = row.get("DTM_mean", 0.0)

                # Store in global dictionary
                if fid is not None:
                    self.fid_dtm_map[str(fid)] = dtm_z

                polygons = []
                if isinstance(geom, Polygon):
                    polygons = [geom]
                elif isinstance(geom, MultiPolygon):
                    polygons = list(geom.geoms)

                for poly in polygons:
                    exterior = poly.exterior.coords[:]
                    points = vtk.vtkPoints()
                    for x, y in exterior:
                        # points.InsertNextPoint(x, y, 0) # Use 0 if no elevation
                        points.InsertNextPoint(x, y, dtm_z)

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
                    actor.GetProperty().SetColor(1.0, 1.0, 0.0)  # Yellow
                    actor.GetProperty().SetLineWidth(2)
                    actor.GetProperty().SetOpacity(1.0)

                    self.renderer.AddActor(actor)
                    self.outline_actors.append(actor)

        self.render_window.Render()

    def load_obj_file_dialog(self):
            file_path, _ = QFileDialog.getOpenFileName(self, "Open OBJ File", "", "OBJ Files (*.obj)")
            if file_path:
                actors = self.read_obj_with_swizzle(file_path)
                if actors:
                    # Remove old ones
                    for act in getattr(self, 'obj_actors', []):
                        self.renderer.RemoveActor(act)

                    self.obj_actors = actors
                    for act in self.obj_actors:
                        self.renderer.AddActor(act)

                    self.renderer.ResetCamera()
                    self.render_window.Render()
                    self.status_label.setText(f"OBJ file loaded with {len(self.obj_actors)} groups:\n{file_path}")

    def read_obj_with_swizzle(self, filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()

        vertices = []
        building_groups = {}  # key: building ID (e.g., G_24_...), value: list of faces
        current_building = "default"

        for line in lines:
            if line.startswith('v '):
                parts = line.strip().split()
                x, y, z = map(float, parts[1:4])
                vertices.append((x, y, z))
            elif line.startswith('g '):
                tokens = line.strip().split()
                # building_ids = [t for t in tokens if t.startswith("G_")]
                if len(tokens) > 1:
                    current_building = tokens[1]  # use the actual group name
                else:
                    current_building = "default"
                # if building_ids:
                #     current_building = building_ids[0]
                # else:
                #     current_building = "default"
                if current_building not in building_groups:
                    building_groups[current_building] = []
            elif line.startswith('f '):
                indices = [int(part.split('/')[0]) - 1 for part in line.strip().split()[1:]]
                if current_building not in building_groups:
                    building_groups[current_building] = []  # <-- add this line
                building_groups[current_building].append(indices)

        self.obj_actors = []

        for building_id, faces in building_groups.items():
            dtm_offset = self.fid_dtm_map.get(str(building_id), 0.0) # If there is no match between g and fid then 0
            
            points = vtk.vtkPoints()
            polys = vtk.vtkCellArray()

            # Using default values for vertex v in OBJ
            # for v in vertices:
            #     points.InsertNextPoint(*v)

            # Apply elevation offset to each vertex before inserting
            for x, y, z in vertices:
                points.InsertNextPoint(x, y, z + dtm_offset)

            for face in faces:
                if len(face) >= 3:
                    polygon = vtk.vtkPolygon()
                    polygon.GetPointIds().SetNumberOfIds(len(face))
                    for i, idx in enumerate(face):
                        polygon.GetPointIds().SetId(i, idx)
                    polys.InsertNextCell(polygon)

            polydata = vtk.vtkPolyData()
            polydata.SetPoints(points)
            polydata.SetPolys(polys)

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(polydata)

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(0.2, 0.6, 1.0)
            actor.GetProperty().SetOpacity(1.0)
            actor.GetProperty().EdgeVisibilityOn()
            actor.group_name = building_id

            self.obj_actors.append(actor)

        return self.obj_actors

    def toggle_slicing_box(self):
        if not self.building_actor and not self.ground_actor:
            self.status_label.setText("No point cloud loaded.")
            return

        if self.clipping_box_enabled:
            # TURN OFF box widget (but keep current clipped result)
            self.clipping_box_widget.Off()
            self.clipping_box_widget.SetInteractor(None)
            self.clipping_box_enabled = False
            self.clipping_box_widget = None

            self.status_label.setText("Slicing disabled (showing last clipped state).")
            self.render_window.Render()
        else:
            # Initialize downsampled versions if needed
            if self.original_ground_polydata and not self.downsampled_ground_polydata:
                self.downsampled_ground_polydata = self.downsample_pointcloud(self.original_ground_polydata, 0.1)
            if self.original_building_polydata and not self.downsampled_building_polydata:
                self.downsampled_building_polydata = self.downsample_pointcloud(self.original_building_polydata, 0.1)

            # Show unclipped downsampled polydata before clipping
            if self.ground_actor and self.downsampled_ground_polydata:
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputData(self.downsampled_ground_polydata)
                self.ground_actor.SetMapper(mapper)

            if self.building_actor and self.downsampled_building_polydata:
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputData(self.downsampled_building_polydata)
                self.building_actor.SetMapper(mapper)

            self.enable_box_clipping()
            self.status_label.setText("Slicing enabled (downsampled).")

    def enable_box_clipping(self):
        if not self.downsampled_ground_polydata and not self.downsampled_building_polydata:
            return

        box_widget = vtk.vtkBoxWidget()
        box_widget.SetInteractor(self.interactor)
        box_widget.SetPlaceFactor(1.0)

        # Prefer placing on building if available
        poly_to_place = self.downsampled_building_polydata or self.downsampled_ground_polydata
        box_widget.SetInputData(poly_to_place)

        if self.last_clipping_bounds:
            box_widget.PlaceWidget(self.last_clipping_bounds)
        else:
            box_widget.PlaceWidget()

        box_widget.GetOutlineProperty().SetColor(1, 1, 0)
        box_widget.GetSelectedOutlineProperty().SetColor(1, 1, 0)
        box_widget.GetOutlineProperty().SetLineWidth(2)
        box_widget.InsideOutOff()
        box_widget.On()

        self.clipping_box_widget = box_widget
        self.clipping_box_enabled = True

        def on_interaction(obj, event):
            planes = vtk.vtkPlanes()
            obj.GetPlanes(planes)
            self.last_clipping_planes = planes

            box_polydata = vtk.vtkPolyData()
            obj.GetPolyData(box_polydata)
            self.last_clipping_bounds = box_polydata.GetBounds()

            for actor, poly in [(self.ground_actor, self.downsampled_ground_polydata),
                                (self.building_actor, self.downsampled_building_polydata)]:
                if actor and poly:
                    clipper = vtk.vtkClipPolyData()
                    clipper.SetInputData(poly)
                    clipper.SetClipFunction(planes)
                    clipper.InsideOutOn()
                    clipper.Update()

                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputConnection(clipper.GetOutputPort())
                    actor.SetMapper(mapper)

            self.render_window.Render()

        box_widget.AddObserver("InteractionEvent", on_interaction)

    def restore_clipping_box(self):
        if not self.clipping_box_widget:
            # If widget was turned off earlier, re-enable it
            self.enable_box_clipping()
            self.status_label.setText("Clipping box restored to full bounds.")
            return

        # Reset the clipping box bounds
        poly_to_place = self.downsampled_building_polydata or self.downsampled_ground_polydata
        if poly_to_place:
            self.clipping_box_widget.SetInputData(poly_to_place)
            self.clipping_box_widget.PlaceWidget()

        # Restore unclipped downsampled views
        if self.ground_actor and self.downsampled_ground_polydata:
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(self.downsampled_ground_polydata)
            self.ground_actor.SetMapper(mapper)

        if self.building_actor and self.downsampled_building_polydata:
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(self.downsampled_building_polydata)
            self.building_actor.SetMapper(mapper)

        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()

        self.status_label.setText("Bounding box and point cloud fully restored.")
        self.last_clipping_planes = None
        self.last_clipping_bounds = None

    def downsample_pointcloud(self, polydata, ratio=0.01):
        """Return a downsampled vtkPolyData by randomly sampling points."""
        n_points = polydata.GetNumberOfPoints()
        n_sample = max(1, int(n_points * ratio))

        ids = np.random.choice(n_points, size=n_sample, replace=False)
        points = vtk.vtkPoints()
        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetName("Colors")

        for i in ids:
            coord = polydata.GetPoint(i)
            color = polydata.GetPointData().GetScalars().GetTuple3(i)
            points.InsertNextPoint(*coord)
            colors.InsertNextTuple3(*color)

        out_poly = vtk.vtkPolyData()
        out_poly.SetPoints(points)
        out_poly.GetPointData().SetScalars(colors)

        glyph = vtk.vtkVertexGlyphFilter()
        glyph.SetInputData(out_poly)
        glyph.Update()
        return glyph.GetOutput()

    def closeEvent(self, event):
        if self.vtk_widget is not None:
            self.vtk_widget.GetRenderWindow().Finalize()
            self.vtk_widget.GetRenderWindow().ReleaseGraphicsResources()
            self.vtk_widget.Finalize()
            self.vtk_widget.deleteLater()
            self.vtk_widget = None

        super().closeEvent(event)