import os
import shutil
from pathlib import Path

def copy_and_rename_csv(root_dir, csv_filename="buildings_data.csv", target_subdir="translated"):
    """
    Copy CSV files from subdirectories to root directory and rename them based on folder name.
    
    Args:
        root_dir (str): Root directory path (e.g., "test")
        csv_filename (str): Name of the CSV file to look for (default: "buildings_data.csv")
        target_subdir (str): Subdirectory name where CSV files are located (default: "translated")
    
    Returns:
        dict: Summary of operations performed
    
    Example:
        # This will copy "test/AF_09_D/translated/buildings_data.csv" to "test/AF_09_D.csv"
        result = copy_and_rename_csv("test")
    """
    
    root_path = Path(root_dir)
    
    if not root_path.exists():
        print(f"Error: Root directory '{root_dir}' does not exist")
        return {"success": False, "error": f"Root directory '{root_dir}' not found"}
    
    if not root_path.is_dir():
        print(f"Error: '{root_dir}' is not a directory")
        return {"success": False, "error": f"'{root_dir}' is not a directory"}
    
    results = {
        "success": True,
        "copied_files": [],
        "failed_files": [],
        "skipped_files": [],
        "total_processed": 0
    }
    
    print(f"Searching for CSV files in: {root_path}")
    print(f"Looking for: {csv_filename} in '{target_subdir}' subdirectories")
    print("=" * 60)
    
    # Iterate through all subdirectories in root_dir
    for item in root_path.iterdir():
        if item.is_dir():
            folder_name = item.name
            csv_source_path = item / target_subdir / csv_filename
            csv_target_path = root_path / f"{folder_name}.csv"
            
            results["total_processed"] += 1
            
            print(f"Processing folder: {folder_name}")
            print(f"  Source: {csv_source_path}")
            print(f"  Target: {csv_target_path}")
            
            # Check if source CSV exists
            if csv_source_path.exists():
                try:
                    # Copy and rename the file
                    shutil.copy2(csv_source_path, csv_target_path)
                    
                    results["copied_files"].append({
                        "folder": folder_name,
                        "source": str(csv_source_path),
                        "target": str(csv_target_path)
                    })
                    
                    print(f"  ✓ Successfully copied to: {csv_target_path.name}")
                    
                except Exception as e:
                    results["failed_files"].append({
                        "folder": folder_name,
                        "source": str(csv_source_path),
                        "error": str(e)
                    })
                    
                    print(f"  ✗ Failed to copy: {e}")
            else:
                results["skipped_files"].append({
                    "folder": folder_name,
                    "source": str(csv_source_path),
                    "reason": "Source file not found"
                })
                
                print(f"  ⚠ Skipped: CSV file not found at {csv_source_path}")
            
            print()  # Empty line for readability
    
    # Print summary
    print("=" * 60)
    print("OPERATION SUMMARY")
    print("=" * 60)
    print(f"Total folders processed: {results['total_processed']}")
    print(f"Successfully copied: {len(results['copied_files'])}")
    print(f"Failed to copy: {len(results['failed_files'])}")
    print(f"Skipped (file not found): {len(results['skipped_files'])}")
    
    if results["copied_files"]:
        print(f"\nSuccessfully copied files:")
        for file_info in results["copied_files"]:
            print(f"  - {file_info['folder']} → {Path(file_info['target']).name}")
    
    if results["failed_files"]:
        print(f"\nFailed files:")
        for file_info in results["failed_files"]:
            print(f"  - {file_info['folder']}: {file_info['error']}")
    
    if results["skipped_files"]:
        print(f"\nSkipped files:")
        for file_info in results["skipped_files"]:
            print(f"  - {file_info['folder']}: {file_info['reason']}")
    
    return results

def copy_and_rename_csv_advanced(root_dir, csv_filename="buildings_data.csv", target_subdir="translated", 
                                 overwrite=True, backup=False):
    """
    Advanced version with more options.
    
    Args:
        root_dir (str): Root directory path
        csv_filename (str): Name of the CSV file to look for
        target_subdir (str): Subdirectory name where CSV files are located
        overwrite (bool): Whether to overwrite existing files (default: True)
        backup (bool): Whether to create backup of existing files (default: False)
    
    Returns:
        dict: Summary of operations performed
    """
    
    root_path = Path(root_dir)
    
    if not root_path.exists():
        return {"success": False, "error": f"Root directory '{root_dir}' not found"}
    
    results = {
        "success": True,
        "copied_files": [],
        "failed_files": [],
        "skipped_files": [],
        "backed_up_files": [],
        "total_processed": 0
    }
    
    print(f"Advanced CSV Copy Operation")
    print(f"Root directory: {root_path}")
    print(f"CSV filename: {csv_filename}")
    print(f"Target subdirectory: {target_subdir}")
    print(f"Overwrite existing: {overwrite}")
    print(f"Create backups: {backup}")
    print("=" * 60)
    
    for item in root_path.iterdir():
        if item.is_dir():
            folder_name = item.name
            csv_source_path = item / target_subdir / csv_filename
            csv_target_path = root_path 
            
            results["total_processed"] += 1
            
            print(f"Processing folder: {folder_name}")
            
            if not csv_source_path.exists():
                results["skipped_files"].append({
                    "folder": folder_name,
                    "reason": "Source file not found"
                })
                print(f"  ⚠ Skipped: Source file not found -> {csv_source_path}")
                continue
            
            # Handle existing target file
            if csv_target_path.exists():
                if backup:
                    backup_path = root_path / f"{folder_name}_backup_{int(Path().stat().st_mtime)}.csv"
                    try:
                        shutil.copy2(csv_target_path, backup_path)
                        results["backed_up_files"].append(str(backup_path))
                        print(f"  📁 Backup created: {backup_path.name}")
                    except Exception as e:
                        print(f"  ⚠ Backup failed: {e}")
                
                if not overwrite:
                    results["skipped_files"].append({
                        "folder": folder_name,
                        "reason": "Target file exists and overwrite=False"
                    })
                    print(f"  ⚠ Skipped: Target file exists")
                    continue
            
            # Copy the file
            try:
                shutil.copy2(csv_source_path, csv_target_path)
                results["copied_files"].append({
                    "folder": folder_name,
                    "source": str(csv_source_path),
                    "target": str(csv_target_path)
                })
                os.rename(csv_source_path, csv_target_path / f"{folder_name}.csv")
                print(f"  ✓ Successfully copied to: {csv_target_path.name}")
                
            except Exception as e:
                results["failed_files"].append({
                    "folder": folder_name,
                    "error": str(e)
                })
                print(f"  ✗ Failed to copy: {e}")
            
            print()
    
    # Print summary
    print("=" * 60)
    print("OPERATION SUMMARY")
    print("=" * 60)
    print(f"Total folders processed: {results['total_processed']}")
    print(f"Successfully copied: {len(results['copied_files'])}")
    print(f"Failed to copy: {len(results['failed_files'])}")
    print(f"Skipped: {len(results['skipped_files'])}")
    if backup:
        print(f"Backup files created: {len(results['backed_up_files'])}")
    
    return results

# Command-line interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Copy and rename CSV files from subdirectories to root directory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python copy_and_rename_csv.py --root_dir test
  python copy_and_rename_csv.py --root_dir "C:/data/test" --csv_name "results.csv"
  python copy_and_rename_csv.py --root_dir test --subdir processed --no-overwrite --backup
  
This will copy files like:
  test/AF_09_D/translated/buildings_data.csv → test/AF_09_D.csv
  test/BG_10_E/translated/buildings_data.csv → test/BG_10_E.csv
        """
    )
    
    parser.add_argument(
        '--root_dir',
        required=True,
        help='Root directory containing subdirectories with CSV files'
    )
    
    parser.add_argument(
        '--csv_name',
        default='buildings_data.csv',
        help='Name of the CSV file to copy (default: buildings_data.csv)'
    )
    
    parser.add_argument(
        '--subdir',
        default='translated',
        help='Subdirectory name where CSV files are located (default: translated)'
    )
    
    parser.add_argument(
        '--no-overwrite',
        action='store_true',
        help='Do not overwrite existing files'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create backup of existing files before overwriting'
    )
    
    args = parser.parse_args()
    
    # Run the function
    result = copy_and_rename_csv_advanced(
        root_dir=args.root_dir,
        csv_filename=args.csv_name,
        target_subdir=args.subdir,
        overwrite=not args.no_overwrite,
        backup=args.backup
    )
    
    if result["success"]:
        print(f"\n✓ Operation completed successfully!")
        return 0
    else:
        print(f"\n✗ Operation failed: {result.get('error', 'Unknown error')}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
