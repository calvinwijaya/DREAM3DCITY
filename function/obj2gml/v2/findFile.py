import os
from pathlib import Path
from collections import defaultdict

def find_and_group_files(root_path, extensions=None):
    """
    Find and group files by directory with specified extensions.
    
    Args:
        root_path (str): Root directory path to search
        extensions (list): List of file extensions to search for
                          Default: ['.obj', '.txt', '.geojson']
    
    Returns:
        list: List of lists, each containing grouped files from same directory
    """
    if extensions is None:
        extensions = ['.obj', '.txt', '.geojson']
    
    # Convert to lowercase for case-insensitive matching
    extensions = [ext.lower() for ext in extensions]
    
    # Dictionary to group files by directory
    files_by_dir = defaultdict(list)
    
    # Convert root_path to Path object
    root = Path(root_path)
    
    # Check if root path exists
    if not root.exists():
        print(f"Error: Root path '{root_path}' does not exist.")
        return []
    
    # Walk through all subdirectories
    for file_path in root.rglob('*'):
        if file_path.is_file():
            # Check if file has one of the target extensions
            if file_path.suffix.lower() in extensions:
                # Group by parent directory
                parent_dir = file_path.parent
                files_by_dir[parent_dir].append(str(file_path))
    
    # Convert to list of lists and sort for consistent output
    result = []
    for directory in sorted(files_by_dir.keys()):
        # Sort files within each directory
        sorted_files = sorted(files_by_dir[directory])
        result.append(sorted_files)
    
    return result

def find_complete_sets(root_path, required_extensions=None):
    """
    Find directories that contain ALL required file types.
    
    Args:
        root_path (str): Root directory path to search
        required_extensions (list): List of required file extensions
                                   Default: ['.obj', '.txt', '.geojson']
    
    Returns:
        list: List of lists, each containing complete sets of files
    """
    if required_extensions is None:
        required_extensions = ['.obj', '.txt', '.geojson']
    
    # Convert to lowercase for case-insensitive matching
    required_extensions = [ext.lower() for ext in required_extensions]
    
    # Dictionary to group files by directory and extension
    files_by_dir = defaultdict(lambda: defaultdict(list))
    
    # Convert root_path to Path object
    root = Path(root_path)
    
    # Check if root path exists
    if not root.exists():
        print(f"Error: Root path '{root_path}' does not exist.")
        return []
    
    # Walk through all subdirectories
    for file_path in root.rglob('*'):
        if file_path.is_file():
            # Check if file has one of the target extensions
            if file_path.suffix.lower() in required_extensions:
                parent_dir = file_path.parent
                extension = file_path.suffix.lower()
                files_by_dir[parent_dir][extension].append(str(file_path))
    
    # Find directories that have all required extensions
    result = []
    for directory, extensions_dict in files_by_dir.items():
        # Check if this directory has all required extensions
        if all(ext in extensions_dict for ext in required_extensions):
            # Create a group with one file from each required extension
            group = []
            for ext in required_extensions:
                # Take the first file of each type (you can modify this logic)
                group.append(extensions_dict[ext][0])
            result.append(group)
    
    # Sort result by directory path
    result.sort(key=lambda x: x[0])
    
    return result

def read_and_convert_txt(file_path):
    """
    Read a txt file and convert comma-separated numbers to dot-separated floats.
    
    Args:
        file_path (str): Path to the txt file
    
    Returns:
        list: List of float numbers with commas replaced by dots
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        result = []
        for line in lines:
            # Strip whitespace and newlines
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Replace comma with dot
            converted_line = line.replace(',', '.')
            
            # Convert to float and add to result
            try:
                number = float(converted_line)
                result.append(number)
            except ValueError:
                print(f"Warning: Could not convert '{line}' to float. Skipping.")
                continue
        
        return result
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

def read_and_convert_txt_as_strings(file_path):
    """
    Alternative version that returns strings instead of floats.
    Useful if you want to preserve the exact format.
    
    Args:
        file_path (str): Path to the txt file
    
    Returns:
        list: List of strings with commas replaced by dots
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        result = []
        for line in lines:
            # Strip whitespace and newlines
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Replace comma with dot
            converted_line = line.replace(',', '.')
            result.append(converted_line)
        
        return result
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []

def batch_process_txt_files(file_paths):
    """
    Process multiple txt files at once.
    
    Args:
        file_paths (list): List of file paths to process
    
    Returns:
        dict: Dictionary with file paths as keys and converted lists as values
    """
    results = {}
    for file_path in file_paths:
        results[file_path] = read_and_convert_txt(file_path)
    return results

# # Example usage and testing
# if __name__ == "__main__":
#     # Test with a sample file
#     def create_test_file():
#         """Create a test file for demonstration"""
#         test_content = """612345,888
# 9123456.123"""
        
#         with open('test_file.txt', 'w') as f:
#             f.write(test_content)
#         print("Test file 'test_file.txt' created!")
    
#     # Create test file
#     create_test_file()
    
#     # Test the function
#     print("=== Testing read_and_convert_txt function ===")
#     result = read_and_convert_txt('test_file.txt')
#     print(f"Result: {result}")
#     print(f"Type of first element: {type(result[0]) if result else 'N/A'}")
    
#     print("\n=== Testing string version ===")
#     result_strings = read_and_convert_txt_as_strings('test_file.txt')
#     print(f"Result (strings): {result_strings}")
    
#     # Test with non-existent file
#     print("\n=== Testing with non-existent file ===")
#     result_error = read_and_convert_txt('non_existent.txt')
#     print(f"Result: {result_error}")
    
#     # Test with multiple files
#     print("\n=== Testing batch processing ===")
#     batch_results = batch_process_txt_files(['test_file.txt', 'non_existent.txt'])
#     for file_path, values in batch_results.items():
#         print(f"{file_path}: {values}")


# # Example usage and testing
# if __name__ == "__main__":
#     # Define your root path here
#     ROOT_PATH = "percepatan_new/OBJ/2025_06_13"  # Change this to your actual root path
    
#     print("=== Method 1: All files grouped by directory ===")
#     grouped_files = find_and_group_files(ROOT_PATH)
    
#     if grouped_files:
#         for i, file_group in enumerate(grouped_files, 1):
#             print(f"Group {i}: {file_group}")
#     else:
#         print("No files found or root path doesn't exist.")
    
#     print("\n=== Method 2: Only complete sets (directories with all 3 file types) ===")
#     complete_sets = find_complete_sets(ROOT_PATH)
    
#     if complete_sets:
#         for i, file_set in enumerate(complete_sets, 1):
#             print(f"Set {i}: {file_set}")
#     else:
#         print("No complete sets found.")

#     print(str(complete_sets[0][0]))
    
#     # Alternative: Create test directory structure
#     def create_test_structure():
#         """Create a test directory structure for demonstration"""
#         import os
        
#         test_dirs = [
#             "root/1",
#             "root/2", 
#             "root/3",
#             "root/subfolder/4"
#         ]
        
#         for dir_path in test_dirs:
#             os.makedirs(dir_path, exist_ok=True)
            
#             # Create test files
#             with open(f"{dir_path}/file.obj", 'w') as f:
#                 f.write("# OBJ file content")
#             with open(f"{dir_path}/file.txt", 'w') as f:
#                 f.write("Text file content")
#             with open(f"{dir_path}/file.geojson", 'w') as f:
#                 f.write('{"type": "FeatureCollection", "features": []}')
        
#         print("Test directory structure created!")
    
#     # Uncomment the line below to create test structure
#     create_test_structure()
