import os
import numpy as np

def read_obj(path):
    vertices = []
    faces = []
    with open(path, "r") as file:
        for line in file:
            if line.startswith("v "):
                parts = line.strip().split()
                vertices.append([float(p) for p in parts[1:]])
            elif line.startswith("f "):
                parts = line.strip().split()
                faces.append([int(p.split('/')[0]) - 1 for p in parts[1:]])
    return np.array(vertices), faces

def compute_face_normal(v0, v1, v2):
    a = v1 - v0
    b = v2 - v0
    normal = np.cross(a, b)
    norm = np.linalg.norm(normal)
    return normal / norm if norm != 0 else normal

def get_face_category(vertices, face, z_min):
    v = np.array([vertices[i] for i in face])
    normal = compute_face_normal(v[0], v[1], v[2])
    
    if np.allclose(v[:, 2], z_min, atol=1e-5):
        return "ground"
    if abs(normal[2]) < 1e-3:
        return "wall"
    return "roof"

def write_mtl(path, colors):
    with open(path, "w") as f:
        for mat_name, rgb in colors.items():
            f.write(f"newmtl {mat_name}\n")
            f.write(f"Kd {rgb[0]:.2f} {rgb[1]:.2f} {rgb[2]:.2f}\n\n")

def write_obj(path, vertices, categorized_faces, mtl_filename):
    with open(path, "w") as f:
        f.write(f"mtllib {mtl_filename}\n")
        for v in vertices:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")
        for material, faces in categorized_faces.items():
            f.write(f"usemtl {material}\n")
            for face in faces:
                f.write("f " + " ".join(str(i + 1) for i in face) + "\n")

def process_obj_file(obj_path, output_folder, colors, index):
    # base = os.path.splitext(os.path.basename(obj_path))[0]

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    base_number = str(index)
    output_obj_path = os.path.join(output_folder, f"{base_number}.obj")
    mtl_filename = f"{base_number}.mtl"
    mtl_path = os.path.join(output_folder, mtl_filename)

    vertices, faces = read_obj(obj_path)
    z_min = np.min(vertices[:, 2])
    categorized_faces = {"ground": [], "wall": [], "roof": []}

    for face in faces:
        category = get_face_category(vertices, face, z_min)
        categorized_faces[category].append(face)

    write_mtl(mtl_path, colors)
    write_obj(output_obj_path, vertices, categorized_faces, mtl_filename)
    print(f"Processed: {obj_path} -> {output_obj_path}")

def coloring_obj(input_folder, output_folder, colors):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    index = 1

    for filename in sorted(os.listdir(input_folder)):
        if filename.lower().endswith(".obj"):
            obj_file_path = os.path.join(input_folder, filename)
            process_obj_file(obj_file_path, output_folder, colors, index)
            index += 1