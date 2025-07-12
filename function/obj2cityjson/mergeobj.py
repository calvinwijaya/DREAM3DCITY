import os
from pathlib import Path
from collections import defaultdict

def merge_obj_mtl(input_folder, output_obj, output_mtl):
    input_folder = Path(input_folder)
    obj_files = sorted(input_folder.glob("*.obj"))
    mtl_files = sorted(input_folder.glob("*.mtl"))

    merged_obj = []
    merged_mtl = []
    material_map = {}  # (original_material, source_file) -> unique_material_name
    material_defs = {}  # unique_material_name -> lines

    v_offset = 0
    vt_offset = 0
    vn_offset = 0

    merged_obj.append(f"mtllib {Path(output_mtl).name}\n")

    for obj_file in obj_files:
        base_name = obj_file.stem
        with open(obj_file, "r") as f:
            lines = f.readlines()

        v_list, vt_list, vn_list = [], [], []
        f_lines = []
        current_material = None

        merged_obj.append(f"o {base_name}\n")

        for line in lines:
            if line.startswith("v "):
                v_list.append(line)
            elif line.startswith("vt "):
                vt_list.append(line)
            elif line.startswith("vn "):
                vn_list.append(line)
            elif line.startswith("usemtl"):
                original = line.strip().split()[1]
                key = (original, base_name)
                if key not in material_map:
                    material_map[key] = f"{base_name}_{original}"
                current_material = material_map[key]
                f_lines.append(f"usemtl {current_material}\n")
            elif line.startswith("f "):
                new_face = []
                for part in line.strip().split()[1:]:
                    indices = part.split("/")
                    vi = int(indices[0]) + v_offset
                    vti = int(indices[1]) + vt_offset if len(indices) > 1 and indices[1] else ''
                    vni = int(indices[2]) + vn_offset if len(indices) > 2 and indices[2] else ''
                    new = f"{vi}"
                    if vti != '' or vni != '':
                        new += f"/{vti}"
                    if vni != '':
                        if vti == '':
                            new += f"/"
                        new += f"/{vni}"
                    new_face.append(new)
                f_lines.append("f " + " ".join(new_face) + "\n")
            elif line.startswith("mtllib") or line.startswith("o "):
                continue  # skip
            else:
                f_lines.append(line)

        merged_obj.extend(v_list)
        merged_obj.extend(vt_list)
        merged_obj.extend(vn_list)
        merged_obj.extend(f_lines)

        v_offset += len(v_list)
        vt_offset += len(vt_list)
        vn_offset += len(vn_list)

    # Merge all MTL files
    for mtl_file in mtl_files:
        source_name = mtl_file.stem
        with open(mtl_file, "r") as f:
            lines = f.readlines()

        current_lines = []
        original = None

        for line in lines:
            if line.startswith("newmtl "):
                if original and current_lines:
                    for (orig_name, src_file), new_name in material_map.items():
                        if orig_name == original and src_file == source_name:
                            material_defs[new_name] = list(current_lines)
                original = line.strip().split()[1]
                current_lines = [f"newmtl {source_name}_{original}\n"]
            elif original:
                current_lines.append(line)

        # Final block
        if original and current_lines:
            for (orig_name, src_file), new_name in material_map.items():
                if orig_name == original and src_file == source_name:
                    material_defs[new_name] = list(current_lines)

    for matname, matlines in material_defs.items():
        merged_mtl.extend(matlines)

    with open(output_obj, "w") as f:
        f.writelines(merged_obj)

    with open(output_mtl, "w") as f:
        f.writelines(merged_mtl)

    print(f"✅ Merge Done:\nOBJ: {output_obj}\nMTL: {output_mtl}")