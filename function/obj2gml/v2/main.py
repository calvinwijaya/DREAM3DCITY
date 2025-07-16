import subprocess as sp
import time
import os
import sys
from tqdm import tqdm
from pathlib import Path
from datetime import datetime

from .findFile import find_complete_sets, read_and_convert_txt
from .cacheHandling import delete_directories, delete_files

from PyQt5.QtCore import QThread, pyqtSignal

class OutputCapture:
    def __init__(self, log_file='processing.log'):
        self.log_file = log_file
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
    def __enter__(self):
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.log_handle = open(self.log_file, 'w', encoding='utf-8')
        sys.stdout = self.log_handle
        sys.stderr = self.log_handle
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.log_handle.close()

class RunObj2GML(QThread):
    progress = pyqtSignal(str)

    def __init__(self, files_dir: str):
        super().__init__()
        self.files_dir = files_dir

    def log_with_timestamp(self, message, is_display: bool =  False):
        """Print message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        if is_display:
            self.progress.emit(f"[{timestamp}] {message}")

    def run_subprocess_with_capture(self, cmd, description=""):
        """Run subprocess and capture ALL its output to the log file"""
        self.log_with_timestamp(f"Starting: {description}")
        self.log_with_timestamp(f"Command: {' '.join(cmd)}")
        
        try:
            # Run subprocess and capture both stdout and stderr
            result = sp.run(
                cmd, 
                stdout=sp.PIPE, 
                stderr=sp.STDOUT,  # Redirect stderr to stdout
                text=True,
                check=False  # Don't raise exception on non-zero return code
            )
            
            # Log the output
            if result.stdout:
                self.log_with_timestamp(f"Command output: {result.stdout}")
                print(result.stdout)
            
            self.log_with_timestamp(f"Command completed with return code: {result.returncode}")
            
            if result.returncode != 0:
                self.log_with_timestamp(f"WARNING: Command failed with return code {result.returncode}")
            
            return result.returncode
            
        except Exception as e:
            self.log_with_timestamp(f"ERROR running command: {str(e)}")
            return -1

    def run(self):
        start = time.time()

        print(f"\n⚙️  Program is running... Please wait 😬🙏")
        
        root_dir = self.files_dir
        tools_dir = "function/obj2gml/v2"
        output_path = f"{root_dir}/CityGML.gml"
    
        temp_dir = f"{root_dir}/temp"
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # Set up log file path
            log_path = f'{root_dir}/detailed_processing.log'.replace('OBJ', 'CityGML')
            
            # Get file set first (before capturing output)
            file_set = find_complete_sets(root_dir)
            
            # Create progress bar OUTSIDE the output capture context
            pbar = tqdm(total=len(file_set), desc="⏳ Processing files", unit="file", 
                        position=0, leave=True, file=sys.__stdout__)
            
            # Capture all output to log file
            with OutputCapture(log_path):
                self.log_with_timestamp("=== PROCESSING STARTED ===", is_display=True)
                self.log_with_timestamp(f"Root directory: {root_dir}")
                self.log_with_timestamp(f"Log file: {log_path}")
                self.log_with_timestamp(f"Found {len(file_set)} file sets to process", is_display=True)
                
                for i, file_data in enumerate(file_set):
                    self.log_with_timestamp(f"--- Processing file set {i+1}/{len(file_set)} ---", is_display=True)
                    
                    obj = file_data[0]
                    coord = read_and_convert_txt(file_data[1])
                    bo = file_data[2]

                    root_path = Path(root_dir)
                    obj_path = Path(obj)

                    rel_path = obj_path.relative_to(root_path)
                    folder_name = rel_path.parts[0]
                    
                    self.log_with_timestamp(f"Processing folder: {folder_name}")
                    self.log_with_timestamp(f"OBJ file: {obj}")
                    self.log_with_timestamp(f"Coordinates: {coord}")
                    self.log_with_timestamp(f"BO file: {bo}")

                    # Update progress bar description (this shows in terminal)
                    pbar.set_description(f"Processing {folder_name}")

                    # define temporary directory
                    obj_dir = f"{temp_dir}/obj"
                    translate_dir = f"{temp_dir}/translated"
                    gml_dir = f"{temp_dir}/citygml"

                    # Step 1: Pemisahan Bangunan
                    self.log_with_timestamp("STEP 1/6: Building separation", is_display=True)
                    self.run_subprocess_with_capture([
                        "go", "run", f"{tools_dir}/objseparator.go", 
                        f"-cx={coord[0]}", f"-cy={coord[1]}",
                        f"{obj}", 
                        f"{bo}",
                        obj_dir
                    ], "Building separation")

                    # Step 2: Translasi Objek Menuju Koordinat UTM
                    self.log_with_timestamp("STEP 2/6: Object translation", is_display=True)
                    self.run_subprocess_with_capture([
                        "go", "run", f"{tools_dir}/translate.go", 
                        f"-input={obj_dir}", 
                        f"-output={translate_dir}", 
                        f"-tx={coord[0]}", 
                        f"-ty={coord[1]}",
                        "-tz=0"
                    ], "Object translation to UTM coordinates")

                    # Step 3: Generate MTL
                    self.log_with_timestamp("STEP 3/6: MTL generation", is_display=True)
                    self.run_subprocess_with_capture([
                        "python", f"{tools_dir}/semantic_mapping.py",
                        "--obj-dir", translate_dir,
                        "--geojson", f"{bo}"
                    ], "MTL generation")

                    # Step 4: Generate attribute
                    self.log_with_timestamp("STEP 4/5: Generate Attribute", is_display=True)
                    self.run_subprocess_with_capture([
                        "python", f"{tools_dir}/attribute_gen.py",
                        "--geojson", f"{tools_dir}/Kelurahan DKI.geojson",
                        "--obj_dir", translate_dir,
                        "--output", translate_dir
                    ])

                    self.run_subprocess_with_capture([
                        "python", f"{tools_dir}/copyNrename.py", "--root_dir", root_dir
                    ])

                    # Step 5: Convert OBJ ke CityGML lod2
                    self.log_with_timestamp("STEP 5/6: OBJ to CityGML conversion", is_display=True)
                    self.run_subprocess_with_capture([
                        "go", "run", f"{tools_dir}/obj2lod2gml.go",
                        "-input", translate_dir,
                        "-output", gml_dir
                    ], "OBJ to CityGML LOD2 conversion")

                    # Step 6: Merge keseluruhan CityGMl lod2 file menjadi 1 file
                    self.log_with_timestamp("STEP 6/6: CityGML file merging", is_display=True)
                    self.run_subprocess_with_capture([
                        "python", f"{tools_dir}/lod2merge.py",
                        gml_dir,
                        f"{output_path}",
                        "--name", f"{folder_name}"
                    ], "CityGML file merging")

                    # Final cleanup
                    self.log_with_timestamp("Final cleanup")
                    self.log_with_timestamp(f"Deleting temporary directories: {temp_dir}")
                    delete_directories([temp_dir])
                    
                    self.log_with_timestamp(f"✅ Completed processing {folder_name}")
                    
                    # Update progress bar (this shows in terminal)
                    pbar.update(1)
                    pbar.set_description(f"✅ Completed all processing")

                end = time.time() - start
                self.log_with_timestamp("=== PROCESSING COMPLETED ===", is_display=True)
                self.log_with_timestamp(f"Total duration: {end:.2f} seconds", is_display=True)
                self.log_with_timestamp(f"Processed {len(file_set)} file sets")
                self.log_with_timestamp(f"Average time per file set: {end/len(file_set):.2f} seconds", is_display=True)
                self.log_with_timestamp(f"📝 Detailed logs with timestamps saved to '{log_path}'", is_display=True)
                self.log_with_timestamp(f"Output file : {output_path}", is_display=True)

            # Close progress bar
            pbar.close()
            
            # This prints to terminal after log capture is done
            print(f"\n🎉 All processing completed!")
            print(f"📊 Processed {len(file_set)} file sets in {end:.2f} seconds")
            print(f"📝 Detailed logs with timestamps saved to '{log_path}'")
            print("\n© 2025. Fairuz Akmal Pradana 👱")
        except Exception as e:
            self.log_with_timestamp(str(e), is_display=True)
