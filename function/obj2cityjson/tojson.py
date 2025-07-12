import os
import json
from tqdm import tqdm
import subprocess
import tempfile

COLORS = {
    "ground": (0.36, 0.25, 0.20),
    "wall": (1.00, 1.00, 1.00),
    "roof": (1.00, 0.00, 0.00)
}

def parse_mtl(mtl_path):
    materials = {}
    current = None
    if not os.path.exists(mtl_path):
        return materials
    with open(mtl_path) as f:
        for line in f:
            if line.startswith('newmtl'):
                current = line.strip().split()[1]
            elif line.startswith('Kd') and current:
                kd = tuple(map(float, line.strip().split()[1:]))
                materials[current] = kd
    return materials

def classify_surface(kd):
    for label, ref in COLORS.items():
        if all(abs(a - b) < 0.01 for a, b in zip(kd, ref)):
            return label
    return "wall"

def parse_obj(obj_path):
    vertices, faces, face_mtls = [], [], []
    current_mtl = None
    mtl_data = {}
    obj_dir = os.path.dirname(obj_path)

    with open(obj_path) as f:
        for line in f:
            if line.startswith('mtllib'):
                mtl_path = os.path.join(obj_dir, line.strip().split()[1])
                mtl_data = parse_mtl(mtl_path)
            elif line.startswith('usemtl'):
                current_mtl = line.strip().split()[1]
            elif line.startswith('v '):
                vertices.append(list(map(float, line.strip().split()[1:])))
            elif line.startswith('f '):
                face = [int(p.split('/')[0]) - 1 for p in line.strip().split()[1:]]
                faces.append(face)
                face_mtls.append(current_mtl)
    return vertices, faces, face_mtls, mtl_data

def create_cityjson(epsg):
    return {
        "type": "CityJSON",
        "version": "1.0",
        "metadata": {
            "referenceSystem": f"urn:ogc:def:crs:EPSG::{epsg}",
            "geographicalExtent": [0, 0, 0, 0, 0, 0]
        },
        "CityObjects": {},
        "vertices": []
    }

def calculate_extent(vertices):
    if not vertices:
        return [0]*6
    xs, ys, zs = zip(*vertices)
    return [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]

def add_to_cityjson(cityjson, building_id, vertices, faces, face_mtls, mtl_data):
    offset = len(cityjson["vertices"])
    cityjson["vertices"].extend(vertices)

    boundaries, semantics_vals, sem_types = [], [], {}

    for face, mtl in zip(faces, face_mtls):
        kd = mtl_data.get(mtl, COLORS["wall"])
        sem = classify_surface(kd).capitalize() + "Surface"
        sem_id = sem_types.setdefault(sem, len(sem_types))
        boundaries.append([[offset + v for v in face]])
        semantics_vals.append(sem_id)

    geometry = {
        "type": "Solid",
        "lod": 2,
        "boundaries": [boundaries],
        "semantics": {
            "surfaces": [{"type": t} for t in sem_types],
            "values": [semantics_vals]
        }
    }

    cityjson["CityObjects"][building_id] = {
        "type": "Building",
        "geometry": [geometry]
    }

def obj_folder_to_cityjson(folder, output_path, epsg):
    cityjson = create_cityjson(epsg)
    obj_files = sorted([f for f in os.listdir(folder) if f.endswith('.obj')])
    with tqdm(total=len(obj_files), desc="Converting .obj") as pbar:
        for fname in obj_files:
            fpath = os.path.join(folder, fname)
            obj_id = os.path.splitext(fname)[0]
            vertices, faces, face_mtls, mtl_data = parse_obj(fpath)
            add_to_cityjson(cityjson, obj_id, vertices, faces, face_mtls, mtl_data)
            pbar.update(1)

    cityjson["metadata"]["geographicalExtent"] = calculate_extent(cityjson["vertices"])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmpfile:
        temp_v1_path = tmpfile.name
        with open(temp_v1_path, 'w') as f:
            json.dump(cityjson, f, indent=2)
    print(f"📝 CityJSON v1.0 saved to: {temp_v1_path}")
    cmd = ["cjio", temp_v1_path, "upgrade", "save", output_path]
    try:
        result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(result.stdout)
        print(f"✅ Saved (v2.0): {output_path}")
    except subprocess.CalledProcessError as e:
        print("❌ CJIO upgrade failed")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
    except Exception as ex:
        print("❌ Unexpected error during CJIO execution")
        print(str(ex))