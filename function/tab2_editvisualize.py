import sys
import os
import json
import shutil
import vtk
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QPushButton, QLabel, QFileDialog, QSizePolicy, QApplication, QComboBox
from PyQt5.QtCore import Qt, QTimer
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from shapely.geometry import shape, Point
from shapely.ops import unary_union
import geopandas as gpd
from collections import OrderedDict

class VisualizeTab(QWidget):
    def __init__(self, folder=None, cityjson_file=None):
        super().__init__()
        self.models = {}
        self.selected_actors = set()
        self.cityjson_data = None
        self.outline_geojsons = []

        main_layout = QHBoxLayout(self)

        # Left panel: buttons + status
        left_panel = QVBoxLayout()
        self.load_button = QPushButton("Load CityJSON File")
        self.load_button.clicked.connect(self.load_cityjson_file_dialog)
        left_panel.addWidget(self.load_button)

        self.reset_button = QPushButton("Reset View")
        self.reset_button.clicked.connect(self.reset_view)
        left_panel.addWidget(self.reset_button)

        self.export_dir = ""  # Default is empty (will fallback to working dir)

        self.choose_dir_button = QPushButton("Choose Export Directory")
        self.choose_dir_button.clicked.connect(self.choose_export_directory)
        left_panel.addWidget(self.choose_dir_button)
        
        self.lod_dropdown = QComboBox()
        self.lod_dropdown.addItems(["1.2", "1.3", "2.2"])
        left_panel.addWidget(QLabel("OBJ Export LOD:"))
        left_panel.addWidget(self.lod_dropdown)

        self.export_button = QPushButton("Export Selection")
        self.export_button.clicked.connect(self.export_selection)
        left_panel.addWidget(self.export_button)      

        self.status_label = QLabel("No CityJSON file loaded")
        self.status_label.setWordWrap(True)
        left_panel.addWidget(self.status_label)

        self.load_outline_button = QPushButton("Load BO *.GeoJSON")
        self.load_outline_button.clicked.connect(self.load_building_outline_geojson)
        left_panel.addWidget(self.load_outline_button)

        self.export_geojson_button = QPushButton("Export Selected BO")
        self.export_geojson_button.clicked.connect(self.export_selected_geojson)
        left_panel.addWidget(self.export_geojson_button)

        left_panel.addStretch()  # push everything to top

        # Right panel: VTK widget
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.vtk_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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

    def load_cityjson_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CityJSON File", "", "CityJSON Files (*.json *.city.json)")
        if file_path:
            print(f"Loading file: {file_path}")  # Debug
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
        vertices = cj.get("vertices", [])
        city_objects = cj.get("CityObjects", {})

        for obj_id, obj in city_objects.items():
            actor = self.create_actor_from_cityobject(obj, vertices)
            if actor:
                self.models[obj_id] = actor
                self.renderer.AddActor(actor)
        self.reset_view()

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

    def on_mouse_click(self, obj, event):
        click_pos = self.interactor.GetEventPosition()
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        actor = self.picker.GetActor()

        shift_pressed = QApplication.keyboardModifiers() == Qt.ShiftModifier

        if actor:
            if shift_pressed:
                if actor in self.selected_actors:
                    actor.GetMapper().ScalarVisibilityOn()
                    self.selected_actors.remove(actor)
                else:
                    actor.GetMapper().ScalarVisibilityOff()
                    actor.GetProperty().SetColor(1.0, 1.0, 0.0)
                    self.selected_actors.add(actor)
            else:
                for a in self.selected_actors:
                    a.GetMapper().ScalarVisibilityOn()
                self.selected_actors.clear()

                actor.GetMapper().ScalarVisibilityOff()
                actor.GetProperty().SetColor(1.0, 1.0, 0.0)
                self.selected_actors.add(actor)

            self.renderer.ResetCameraClippingRange()
            self.render_window.Render()

    def export_selection(self):
        if not self.cityjson_data:
            return

        selected_lod = self.lod_dropdown.currentText()
        vertices = self.cityjson_data.get("vertices", [])
        city_objects = self.cityjson_data.get("CityObjects", {})
        selected_ids = [obj_id for obj_id, actor in self.models.items() if actor in self.selected_actors]

        # Get base name for export files
        input_filename = self.cityjson_data.get("_input_filename", "export")  # fallback
        base_name = os.path.splitext(os.path.basename(input_filename))[0]
        export_dir = self.export_dir if self.export_dir else os.getcwd()
        obj_filename = os.path.join(export_dir, f"{base_name}_selection.obj")
        cropped_filename = os.path.join(export_dir, f"{base_name}_cropped.json")

        # Export OBJ with selected LOD
        obj_lines = [f"v {v[0]} {v[1]} {v[2]}" for v in vertices]
        for obj_id in selected_ids:
            obj = city_objects[obj_id]
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

        # Crop CityJSON to LOD 2.2 only
        filtered_city_objects = {}
        for obj_id, obj in city_objects.items():
            if obj_id in selected_ids:
                continue
            filtered_geoms = [g for g in obj.get("geometry", []) if g.get("lod") == "2.2"]
            if filtered_geoms:
                new_obj = obj.copy()
                new_obj["geometry"] = filtered_geoms
                filtered_city_objects[obj_id] = new_obj

        all_child_ids = set(filtered_city_objects.keys())
        for obj_id, obj in city_objects.items():
            if obj_id not in filtered_city_objects:
                continue
            if "parents" in obj:
                for parent_id in obj["parents"]:
                    if parent_id not in filtered_city_objects and parent_id in city_objects:
                        filtered_city_objects[parent_id] = city_objects[parent_id]

        cropped_cityjson = OrderedDict()
        cropped_cityjson["type"] = "CityJSON"
        cropped_cityjson["version"] = self.cityjson_data.get("version", "2.0")

        transform = self.cityjson_data.get("transform")
        if transform:
            cropped_cityjson["transform"] = transform

        if "metadata" in self.cityjson_data:
            cropped_cityjson["metadata"] = self.cityjson_data["metadata"]

        cropped_cityjson["CityObjects"] = filtered_city_objects
        cropped_cityjson["vertices"] = vertices

        with open(cropped_filename, "w") as f:
            json.dump(cropped_cityjson, f, indent=2)

        self.status_label.setText(f"Exported:\n - {obj_filename}\n - {cropped_filename}")

    def reset_view(self):
        self.renderer.GetActiveCamera().SetPosition(0, 0, 1)
        self.renderer.GetActiveCamera().SetFocalPoint(0, 0, 0)
        self.renderer.GetActiveCamera().SetViewUp(0, 1, 0)
        self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()

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
                out_path = os.path.join(export_dir, f"{basename}_selected.geojson")
                new_gdf.to_file(out_path, driver="GeoJSON")
                exported_files.append(out_path)

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

