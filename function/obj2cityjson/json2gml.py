import os
import subprocess

def json2gml(cityjson_path):
    # Get absolute paths
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tools_dir = os.path.join(project_root, "citygml-tools-2.4.0")
    bat_path = os.path.join(tools_dir, "citygml-tools.bat")

    if not os.path.exists(bat_path):
        print(f"❌ citygml-tools.bat not found at: {bat_path}")
        return

    cmd = [bat_path, "from-cityjson", cityjson_path]

    try:
        result = subprocess.run(cmd, cwd=tools_dir, check=True, text=True, capture_output=True)
        print("✅ CityJSON successfully converted to CityGML")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("❌ CityGML conversion failed")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
    except Exception as ex:
        print("❌ Unexpected error during CityGML conversion")
        print(str(ex))