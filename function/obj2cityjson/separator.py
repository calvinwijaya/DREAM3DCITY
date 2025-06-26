import os
import uuid
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
from datetime import datetime

def parse_obj_with_group(obj_path):
    vertices = []
    group_faces = {}
    current_group = None

    with open(obj_path, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = list(map(float, line.strip().split()[1:4]))
                vertices.append(parts)
            elif line.startswith('g '):
                current_group = line.strip().split()[1]
                if current_group not in group_faces:
                    group_faces[current_group] = []
            elif line.startswith('f '):
                face = [int(part.split('/')[0]) - 1 for part in line.strip().split()[1:]]
                group_faces[current_group].append(face)
    return np.array(vertices), group_faces

def save_obj_worker(args):
    uuid, faces, original_vertices, index_map, output_dir, delta_z = args
    obj_filename = f"{uuid}.obj"
    obj_path = os.path.join(output_dir, obj_filename)

    with open(obj_path, 'w') as f:
        f.write(f"g {uuid}\n")
        for i in index_map:
            v = original_vertices[i]
            f.write(f"v {v[0]} {v[1]} {v[2] + delta_z:.6f}\n")
        for face in faces:
            mapped = [str(index_map[idx] + 1) for idx in face]
            f.write(f"f {' '.join(mapped)}\n")

def increment_string(s):
    s = list(s)
    i = len(s) - 1
    while i >= 0:
        if s[i] != 'Z':
            s[i] = chr(ord(s[i]) + 1)
            return ''.join(s)
        s[i] = 'A'
        i -= 1
    return 'A' + ''.join(s)

def generate_auto_uuid(prefix, date_str, code_prefix, number, user):
    random_part = uuid.uuid4().hex[:7].upper()
    return f"{prefix}_{date_str}-{code_prefix}-{number:05d}-{user}-{random_part}"

def split_obj_by_geojson(obj_path, geojson_path, output_dir, origin_utm, uuid_prefix='Bontang', user='Digital Twin UGM', output_geojson_path=None):
    if uuid_prefix is None:
        obj_name = os.path.basename(obj_path)
        obj_stem = os.path.splitext(obj_name)[0]
        uuid_prefix = str(obj_stem)
    if user is None:
        user = 'Digital_Twin_UGM'
    
    os.makedirs(output_dir, exist_ok=True)

    print("📦 Reading OBJ...")
    vertices, group_faces = parse_obj_with_group(obj_path)

    utm_vertices = vertices.copy()
    utm_vertices[:, 0] += origin_utm[0]
    utm_vertices[:, 1] += origin_utm[1]

    print("🌍 Write GeoJSON...")
    gdf = gpd.read_file(geojson_path)

    auto_uuid_number = 1
    auto_uuid_code = "AAAA"
    date_str = datetime.today().strftime("%d%m%Y")  # Format: 23052025

    if "UUID" not in gdf.columns:
        print("⚠️  'UUID' Column is not found, created automatically...")
        gdf["UUID"] = None

    for idx in gdf.index:
        if gdf.at[idx, "UUID"] is None:
            uuid_val = generate_auto_uuid(uuid_prefix, date_str, auto_uuid_code, auto_uuid_number, user)
            gdf.at[idx, "UUID"] = uuid_val
            auto_uuid_number += 1
            if auto_uuid_number > 99999:
                auto_uuid_code = increment_string(auto_uuid_code)
                auto_uuid_number = 1

    if output_geojson_path:
        gdf.to_file(output_geojson_path, driver="GeoJSON")
        print(f"📝 GeoJSON with UUID saved to: {output_geojson_path}")

    uuid_faces = {}
    uuid_indices = {}

    for idx, row in gdf.iterrows():
        uuid_val = row["UUID"]
        uuid_faces[uuid_val] = []
        uuid_indices[uuid_val] = set()

    print("🔍 Grouping with UUID GeoJSON...")
    for group_name, faces in tqdm(group_faces.items(), desc="Memetakan grup"):
        if not faces:
            continue
        sample_face = faces[0]
        face_vertices = [utm_vertices[idx] for idx in sample_face]
        center = np.mean(face_vertices, axis=0)
        point = Point(center[0], center[1])

        matched_uuid = None
        for idx, row in gdf.iterrows():
            if row['geometry'].contains(point):
                matched_uuid = row['UUID']
                break

        if matched_uuid in uuid_faces:
            uuid_faces[matched_uuid].extend(faces)
            for face in faces:
                uuid_indices[matched_uuid].update(face)

    print("💾 Saving OBJ after separation (multiprocessing)...")
    tasks = []
    for uuid_val in uuid_faces:
        if uuid_faces[uuid_val]:
            indices = sorted(uuid_indices[uuid_val])
            index_map = {old: new for new, old in enumerate(indices)}

            group_vertices = utm_vertices[indices]
            z_min_local = group_vertices[:, 2].min()
            delta_z = origin_utm[2] - z_min_local

            tasks.append((uuid_val, uuid_faces[uuid_val], utm_vertices, index_map, output_dir, delta_z))

    with Pool(processes=max(1, cpu_count() - 1)) as pool:
        list(tqdm(pool.imap_unordered(save_obj_worker, tasks), total=len(tasks), desc="Menyimpan hasil"))

    print("✅ DONE. All files saved to:", output_dir)