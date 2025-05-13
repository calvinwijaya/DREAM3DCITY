import os
import json
from tqdm import tqdm

def parse_obj_with_building_groups(file_path):
    vertices = []
    buildings = {}
    current_group = "Building_0"
    current_material = None

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
                    buildings[current_group] = {"faces": [], "materials": []}
            elif parts[0] == 'usemtl':
                current_material = parts[1]
            elif parts[0] == 'f':
                face_indices = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                if current_group not in buildings:
                    buildings[current_group] = {"faces": [], "materials": []}
                buildings[current_group]["faces"].append(face_indices)
                buildings[current_group]["materials"].append(current_material)

    return vertices, buildings

def create_cityjson_structure():
    return {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {
            "scale": [1, 1, 1],
            "translate": [0, 0, 0]
        },
        "CityObjects": {},
        "vertices": [],
        "appearance": {
            "materials": {
                "": [
                    {"name": "roof", "diffuseColor": [1.0, 0.0, 0.0], "isSmooth": False},
                    {"name": "wall", "diffuseColor": [0.8, 0.8, 0.8], "isSmooth": False},
                    {"name": "ground", "diffuseColor": [0.4, 0.25, 0.1], "isSmooth": False}
                ]
            }
        }
    }

def calculate_geographical_extent(vertices):
    if not vertices:
        return [0, 0, 0, 0, 0, 0]
    
    transposed = list(zip(*vertices))
    xmin, ymin, zmin = map(min, transposed)
    xmax, ymax, zmax = map(max, transposed)
    return [xmin, ymin, zmin, xmax, ymax, zmax]

def add_building_with_materials(cityjson, building_id, vertices, faces, materials, building_index, roof_color='Color_A01', ground_color='Color_G01'):
    solid_geometry = []
    semantics_values = []
    material_values = []

    for i, face in enumerate(faces):
        solid_geometry.append([[idx for idx in face]])

        mat = materials[i]
        if mat == roof_color:
            semantics_values.append(0)  # RoofSurface
            material_values.append(0)
        elif mat == ground_color:
            semantics_values.append(2)  # GroundSurface
            material_values.append(2)
        else:
            semantics_values.append(1)  # Default to WallSurface
            material_values.append(1)

    geometry = {
        "type": "Solid",
        "lod": "2.2",  # changed from 2 to "2.2"
        "boundaries": [solid_geometry],
        "semantics": {
            "values": [semantics_values],
            "surfaces": [
                {"type": "RoofSurface"},
                {"type": "WallSurface"},
                {"type": "GroundSurface"}
            ]
        },
        "material": {
            "": {
                "values": [material_values]
            }
        }
    }

    cityjson["CityObjects"][building_id] = {
        "type": "Building",
        "geometry": [geometry],
        "attributes": {
            "Id": building_index + 1
        }
    }

def save_cityjson(cityjson, output_file):
    with open(output_file, 'w') as f:
        json.dump(cityjson, f, indent=2)

def obj_to_cityjson_multiple_buildings(input_file, output_file, roof_color, ground_color):
    vertices, buildings = parse_obj_with_building_groups(input_file)
    cityjson = create_cityjson_structure()

    cityjson["vertices"] = vertices
    
    for i, (building_id, data) in enumerate(buildings.items()):
        add_building_with_materials(
            cityjson,
            building_id,
            vertices,
            data["faces"],
            data["materials"],
            i,
            roof_color, 
            ground_color
        )
    
    save_cityjson(cityjson, output_file)
    print(f"\n✅ CityJSON saved with {len(buildings)} buildings: {output_file}")