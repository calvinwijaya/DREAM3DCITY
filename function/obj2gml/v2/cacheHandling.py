import os
import shutil

def delete_files(directory):
    files_to_delete = ["12030.obj", "12030.mtl", "12030.gml"]
    
    for filename in files_to_delete:
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Deleted: {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        else:
            print(f"File not found: {file_path}")

def delete_directories(directories):
    for directory in directories:
        if os.path.exists(directory) and os.path.isdir(directory):
            try:
                shutil.rmtree(directory)
                print(f"Deleted directory: {directory}")
            except Exception as e:
                print(f"Error deleting directory {directory}: {e}")
        else:
            print(f"Directory not found or not a directory: {directory}")
