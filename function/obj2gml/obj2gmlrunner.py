import subprocess as sp
import time
import sys
from pathlib import Path
import shutil

start = time.time()

obj_path = Path(sys.argv[1])
obj_stem = obj_path.stem
bo_path = sys.argv[2]
tx = float(sys.argv[3])
ty = float(sys.argv[4])
epsg = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] else "32748"

# Optional args (prefix and author)
prefix = sys.argv[5] if sys.argv[5] else None
if prefix == "" or prefix is None:
    prefix = obj_stem

user = sys.argv[6] if sys.argv[6] else None
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

# Building Separator
go_run("objseparator.go",
       f"-cx={tx}", f"-cy={ty}",
       str(obj_path), bo_path)

# ✅ Delete 12030.obj if it exists
invalid_obj = export_path / "12030.obj"
if invalid_obj.exists():
    invalid_obj.unlink()

# Translate OBJ
go_run("translate.go",
       f"-input={export_path}",
       f"-tx={tx}", f"-ty={ty}", "-tz=0")

# # Generate MTL
python_run("semantic_mapping.py",
            "--obj-dir", f"{export_path}_translated",
            "--geojson", bo_path,)

# Convert OBJ to GML
go_run("obj2lod2gml.go",
       "-input", f"{export_path}_translated",
       "-output", f"{export_path}_translated_gml",
       "-epsg", epsg)
    
# Merge GML
python_run("lod2merge.py",
             f"{export_path}_translated_gml",
             str(obj_path.parent / f"{obj_stem}.gml"),
             "--bo", bo_path,
             "--name", prefix,
             "--author", user)

print(f"✅ Finished in {time.time() - start:.2f}s")

# ✅ Clean up all temp folders
for temp_folder in [
    export_path,
    export_path.with_name(f"{export_path.name}_translated"),
    export_path.with_name(f"{export_path.name}_translated_gml")
]:
    if temp_folder.exists() and temp_folder.is_dir():
        shutil.rmtree(temp_folder)