import json
import numpy as np
from shapely.geometry import shape, Polygon, LineString, Point, LineString
from shapely.ops import unary_union
from collections import defaultdict
from shapely.geometry import Polygon as ShapelyPolygon
from scipy.spatial import KDTree
from scipy.spatial.transform import Rotation as R
from sklearn.cluster import KMeans

def compute_face_normal(vertices, face):
    v = [vertices[v_idx] for v_idx, _ in face]
    if len(v) >= 3:
        normal = np.cross(v[1] - v[0], v[2] - v[0])
        return normal / np.linalg.norm(normal) if np.linalg.norm(normal) > 0 else np.array([0, 0, 1])
    return np.array([0, 0, 1])

def load_obj_with_groups(file_path):
    vertices = []
    buildings = {}
    current_group = "Building_0"

    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == 'v':
                vertices.append([float(coord) for coord in parts[1:]])
            elif parts[0] == 'g':
                current_group = parts[1]
                if current_group not in buildings:
                    buildings[current_group] = []
            elif parts[0] == 'f':
                face_indices = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                buildings[current_group].append(face_indices)

    return np.array(vertices), buildings

def face_centroid(vertices, face):
    return np.mean([vertices[v_idx] for v_idx, _ in face], axis=0)

def classify_faces(vertices, normals, faces, ground_angle_threshold=30, wall_min_angle=60, wall_max_angle=120, outwardness_threshold=0.3):    
    classified = defaultdict(list)
    z_axis = np.array([0, 0, 1])
    centroids = np.array([face_centroid(vertices, f) for f in faces])
    center_z = np.median(centroids[:, 2])
    building_center = np.mean(centroids, axis=0)

    for idx, face in enumerate(faces):
        normal = normals[idx]
        if np.linalg.norm(normal) == 0:
            continue
        normal = normal / np.linalg.norm(normal)
        centroid = centroids[idx]

        angle_to_z = np.degrees(np.arccos(np.clip(np.dot(normal, z_axis), -1.0, 1.0)))

        horizontal_vec = centroid - building_center
        horizontal_vec[2] = 0 
        if np.linalg.norm(horizontal_vec) == 0:
            horizontal_vec = np.array([0, 0, 1])
        horizontal_vec = horizontal_vec / np.linalg.norm(horizontal_vec)

        outwardness = np.dot(normal[:2], horizontal_vec[:2])

        if angle_to_z < ground_angle_threshold:
            if centroid[2] < center_z:
                classified['GroundSurface'].append(face)
            else:
                classified['RoofSurface'].append(face)
        elif wall_min_angle <= angle_to_z <= wall_max_angle:
            if outwardness > outwardness_threshold:
                classified['WallSurface'].append(face)
            else:
                classified['RoofSurface'].append(face)
        else:
            if centroid[2] > center_z:
                classified['RoofSurface'].append(face)
            else:
                classified['WallSurface'].append(face)

    return classified

def generate_cityjson(vertices, classified_faces):
    cj_faces = []
    semantics_values = []
    surface_types = ['RoofSurface', 'WallSurface', 'GroundSurface']

    vertex_index_map = {}
    raw_vertices = []

    def get_index(v):
        v_tuple = tuple(np.round(v, 6)) 
        if v_tuple not in vertex_index_map:
            vertex_index_map[v_tuple] = len(raw_vertices)
            raw_vertices.append(v_tuple)
        return vertex_index_map[v_tuple]

    for idx, surface in enumerate(surface_types):
        for face in classified_faces[surface]:
            indices = [get_index(vertices[v_idx]) for v_idx, _ in face]
            cj_faces.append([indices])
            semantics_values.append(idx)

    raw_vertices = np.array(raw_vertices)
    min_vals = raw_vertices.min(axis=0)
    scale = [0.01, 0.01, 0.01]  # 1 cm
    translate = min_vals.tolist()
    int_vertices = np.round((raw_vertices - min_vals) / scale).astype(int).tolist()

    cityjson = {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {
            "scale": scale,
            "translate": translate
        },
        "CityObjects": {
            "building-1": {
                "type": "Building",
                "geometry": [{
                    "type": "Solid",
                    "lod": "2.2",
                    "boundaries": [cj_faces],
                    "semantics": {
                        "surfaces": [{"type": t} for t in surface_types],
                        "values": [semantics_values]
                    }
                }]
            }
        },
        "vertices": int_vertices
    }

    return cityjson