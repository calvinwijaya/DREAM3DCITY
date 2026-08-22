import json
import os

def process_roofer_output(jsonl_path, out_dir, base_name):
    """
    Parses a Roofer CityJSONL file.
    Outputs a merged CityJSON (.json), an OBJ (.obj), and an MTL (.mtl).
    """
    cityjson_path = os.path.join(out_dir, f"{base_name}.json")
    obj_path = os.path.join(out_dir, f"{base_name}.obj")
    mtl_path = os.path.join(out_dir, f"{base_name}.mtl")

    if not os.path.exists(jsonl_path):
        return False, "Input JSONL not found."

    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            return False, "JSONL file is empty."

        # Parse Line 1: Main CityJSON metadata
        main_cj = json.loads(lines[0])
        main_cj["CityObjects"] = {}
        if "vertices" not in main_cj:
            main_cj["vertices"] = []

        scale = main_cj.get("transform", {}).get("scale", [1.0, 1.0, 1.0])
        translate = main_cj.get("transform", {}).get("translate", [0.0, 0.0, 0.0])

        obj_vertices = []
        obj_faces = []

        # Parse Line 2+: Features
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            feat = json.loads(line)
            
            # Offset vertices for CityJSON continuity
            v_offset = len(main_cj["vertices"])
            main_cj["vertices"].extend(feat.get("vertices", []))
            
            # Convert scaled vertices into real-world coordinates for OBJ
            for v in feat.get("vertices", []):
                rx = v[0] * scale[0] + translate[0]
                ry = v[1] * scale[1] + translate[1]
                rz = v[2] * scale[2] + translate[2]
                obj_vertices.append((rx, ry, rz))

            for co_id, co in feat.get("CityObjects", {}).items():
                for geom in co.get("geometry", []):
                    # Shift indices so they align with the global array
                    _offset_geometry(geom.get("boundaries", []), v_offset)
                    # Map faces to materials
                    _extract_obj_faces(geom, obj_faces)
                main_cj["CityObjects"][co_id] = co

        # 1. Output Standard CityJSON
        with open(cityjson_path, 'w', encoding='utf-8') as f:
            json.dump(main_cj, f, separators=(',', ':'))

        # 2. Output MTL Definitions
        _write_mtl(mtl_path)

        # 3. Output 3D OBJ
        _write_obj(obj_path, base_name, obj_vertices, obj_faces)

        return True, "Success"
    except Exception as e:
        return False, str(e)


def _offset_geometry(boundaries, offset):
    """Recursively updates vertex indices in CityJSON boundaries."""
    if isinstance(boundaries, list):
        for i in range(len(boundaries)):
            if isinstance(boundaries[i], int):
                boundaries[i] += offset
            else:
                _offset_geometry(boundaries[i], offset)


def _extract_obj_faces(geom, obj_faces):
    """Extracts exterior rings from boundaries and assigns material based on CityJSON semantics."""
    geom_type = geom.get("type")
    boundaries = geom.get("boundaries", [])
    semantics = geom.get("semantics", {})
    surfaces = semantics.get("surfaces", [])
    values = semantics.get("values", [])

    def get_mtl(surf_idx):
        if surf_idx is None or not isinstance(surf_idx, int) or surf_idx < 0 or surf_idx >= len(surfaces):
            return "0"  # Default
        stype = surfaces[surf_idx].get("type", "")
        if stype == "WallSurface": return "1"
        if stype == "RoofSurface": return "2"
        if stype == "GroundSurface": return "0"
        return "3"

    if geom_type == "Solid":
        for shell_idx, shell in enumerate(boundaries):
            for poly_idx, poly in enumerate(shell):
                if not poly: continue
                ext_ring = poly[0] # The first ring is always the exterior
                
                surf_idx = None
                try:
                    surf_idx = values[shell_idx][poly_idx]
                except:
                    pass
                
                mtl = get_mtl(surf_idx)
                # OBJ uses 1-based indexing for vertices
                face_v = [v + 1 for v in ext_ring]
                obj_faces.append((mtl, face_v))
                
    elif geom_type == "MultiSurface":
        for poly_idx, poly in enumerate(boundaries):
            if not poly: continue
            ext_ring = poly[0]
            
            surf_idx = None
            try:
                surf_idx = values[poly_idx]
            except:
                pass
            
            mtl = get_mtl(surf_idx)
            face_v = [v + 1 for v in ext_ring]
            obj_faces.append((mtl, face_v))


def _write_mtl(mtl_path):
    """Writes standard material profiles replicating Geoflow outputs."""
    mtl_content = (
        "newmtl 1\nKa 0.8700 0.2600 0.2800\nKd 0.8700 0.2600 0.2800\nKs 0.8700 0.2600 0.2800\nillum 2\nNs 60.0000\n\n"
        "newmtl 2\nKa 0.9000 0.9000 0.7500\nKd 0.9000 0.9000 0.7500\nKs 0.9000 0.9000 0.7500\nillum 2\nNs 60.0000\n\n"
        "newmtl 3\nKa 0.9000 0.9000 0.7500\nKd 0.9000 0.9000 0.7500\nKs 0.9000 0.9000 0.7500\nillum 2\nNs 60.0000\n\n"
        "newmtl 0\nKa 0.6000 0.6000 0.6000\nKd 0.6000 0.6000 0.6000\nKs 0.6000 0.6000 0.6000\nillum 2\nNs 60.0000\n"
    )
    with open(mtl_path, 'w', encoding='utf-8') as f:
        f.write(mtl_content)


def _write_obj(obj_path, base_name, vertices, faces):
    """Writes the .obj file, chunking by materials."""
    with open(obj_path, 'w', encoding='utf-8') as f:
        f.write(f"# Generated by DREAM 3D CITY Roofer Parser\n")
        f.write(f"mtllib {base_name}.mtl\n")
        
        for v in vertices:
            f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
        
        current_mtl = None
        for mtl, face_v in faces:
            if mtl != current_mtl:
                f.write(f"usemtl {mtl}\n")
                current_mtl = mtl
            f.write("f " + " ".join(str(idx) for idx in face_v) + "\n")