import subprocess as sp
import time
import sys
from pathlib import Path
import shutil

start = time.time()

obj_path = Path(sys.argv[1])
obj_stem = obj_path.stem
bo_path = sys.argv[2]
epsg = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else "32748"
obj_name = Path(sys.argv[6])
obj_name_stem = obj_name.stem

# Optional args (prefix and author)
prefix = sys.argv[3] if sys.argv[3] else None
if prefix == "" or prefix is None:
    prefix = obj_stem

user = sys.argv[4] if sys.argv[4] else None
if user == "" or user is None:
    user = "Digital_Twin_UGM"

# Base path where the Go scripts are located
base_dir = Path(__file__).resolve().parent

# Extract identifiers
export_path = obj_path.parent / f"temp_{obj_stem}"

def go_run(script, *args):
    return sp.call(
        ["go", "run", str(base_dir / script), *args],
        cwd=base_dir,
        shell=False
    )

def python_run(script, *args):
    return sp.call(
        ["python", str(base_dir / script), *args],
        cwd=base_dir,
        shell=False
    )

# Convert OBJ to GML
go_run("obj2lod2gml.go",
       "-input", obj_path,
       "-output", f"{export_path}_gml",
       "-epsg", epsg)
    
# Merge GML
python_run("lod2merge.py",
             f"{export_path}_gml",
             str(obj_path.parent / f"{obj_name_stem}.gml"),
             "--bo", bo_path,
             "--name", prefix,
             "--author", user)

print(f"✅ Finished in {time.time() - start:.2f}s")

# ✅ Clean up all temp folders
for temp_folder in [
    export_path,
    export_path.with_name(f"{export_path.name}_gml")
]:
    if temp_folder.exists() and temp_folder.is_dir():
        shutil.rmtree(temp_folder)