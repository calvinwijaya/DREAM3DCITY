import os
import json
import csv
import math
import argparse
import random
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point, Polygon
from shapely.ops import transform
import pyproj
from functools import partial

class OBJToCSVGenerator:
    def __init__(self, geojson_path, obj_folder_path, output_folder_path):
        self.geojson_path = geojson_path
        self.obj_folder_path = obj_folder_path
        self.output_folder_path = output_folder_path
        
        # Indonesian names for random generation
        self.first_names = [
            "Ahmad", "Budi", "Sari", "Dewi", "Andi", "Rina", "Joko", "Maya", "Rudi", "Sinta",
            "Agus", "Lina", "Hadi", "Ratna", "Dedi", "Indira", "Bambang", "Fitri", "Wahyu", "Novi",
            "Teguh", "Yuni", "Fajar", "Dian", "Hendro", "Wati", "Gunawan", "Siti", "Rizki", "Ayu",
            "Bayu", "Eka", "Doni", "Mega", "Irwan", "Tuti", "Yoga", "Lia", "Eko", "Nita",
            "Arif", "Rini", "Dimas", "Sri", "Hendra", "Ani", "Yanto", "Dwi", "Adi", "Tri"
        ]
        
        self.last_names = [
            "Wijaya", "Santoso", "Pratama", "Sari", "Kusuma", "Utama", "Permana", "Lestari",
            "Rahayu", "Handoko", "Susanto", "Maharani", "Purnama", "Wardani", "Setiawan", "Anggraini",
            "Nugroho", "Safitri", "Kurniawan", "Wulandari", "Hidayat", "Pertiwi", "Suryanto", "Cahyani",
            "Gunawan", "Sulistyowati", "Irawan", "Novitasari", "Suryana", "Oktaviani", "Pranoto", "Fitriani",
            "Saputra", "Puspitasari", "Hermawan", "Damayanti", "Setiadi", "Kusumawardani", "Haryanto", "Widyastuti"
        ]
        
        self.middle_names = [
            "Budi", "Sari", "Dwi", "Tri", "Eka", "Dua", "Agung", "Indah", "Jaya", "Mulia",
            "Putra", "Putri", "Adi", "Ayu", "Bayu", "Devi", "Fajar", "Gita", "Hadi", "Ika"
        ]
        
        # Load administrative boundaries
        print(f"Loading GeoJSON from: {geojson_path}")
        self.gdf = gpd.read_file(geojson_path)
        print(f"Loaded {len(self.gdf)} administrative boundaries")
        
        # Create unique codes for administrative areas
        self.create_admin_codes()
        
        # Ensure output folder exists
        os.makedirs(output_folder_path, exist_ok=True)
        print(f"Output directory created/verified: {output_folder_path}")
    
    def generate_indonesian_name(self):
        """Generate random Indonesian name with 2 or 3 words"""
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        
        # 60% chance for 2 words, 40% chance for 3 words
        if random.random() < 0.6:
            # 2 words
            return f"{first_name} {last_name}"
        else:
            # 3 words
            middle_name = random.choice(self.middle_names)
            return f"{first_name} {middle_name} {last_name}"
    
    def format_nop(self, nop_digits):
        """Format 18-digit NOP into XX.XX.XXX.XXX.XXX-XXXX.X pattern"""
        if len(nop_digits) != 18:
            # Ensure exactly 18 digits
            nop_digits = nop_digits.ljust(18, '0')[:18]
        
        # Format: XX.XX.XXX.XXX.XXX-XXXX.X
        formatted = f"{nop_digits[0:2]}.{nop_digits[2:4]}.{nop_digits[4:7]}.{nop_digits[7:10]}.{nop_digits[10:13]}-{nop_digits[13:17]}.{nop_digits[17]}"
        return formatted
    
    def create_admin_codes(self):
        """Create unique 2-digit codes for WADMKK, WADMKC, and 3-digit for WADMKD"""
        
        # Get unique values and create codes
        unique_kota = self.gdf['WADMKK'].dropna().unique()
        unique_kecamatan = self.gdf['WADMKC'].dropna().unique()
        unique_kelurahan = self.gdf['WADMKD'].dropna().unique()
        
        # Create mapping dictionaries
        self.kota_codes = {kota: f"{i+1:02d}" for i, kota in enumerate(unique_kota)}
        self.kecamatan_codes = {kec: f"{i+1:02d}" for i, kec in enumerate(unique_kecamatan)}
        self.kelurahan_codes = {kel: f"{i+1:03d}" for i, kel in enumerate(unique_kelurahan)}
        
        print("Administrative Codes Created:")
        print(f"  - Kota codes: {len(self.kota_codes)} entries")
        print(f"  - Kecamatan codes: {len(self.kecamatan_codes)} entries")
        print(f"  - Kelurahan codes: {len(self.kelurahan_codes)} entries")
    
    def parse_obj_file(self, obj_path):
        """Parse OBJ file to extract vertices and faces"""
        vertices = []
        faces = []
        
        try:
            with open(obj_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if line.startswith('v '):  # Vertex
                        parts = line.split()
                        if len(parts) >= 4:
                            try:
                                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                                vertices.append((x, y, z))
                            except ValueError:
                                print(f"Warning: Invalid vertex at line {line_num} in {obj_path}")
                    elif line.startswith('f '):  # Face
                        parts = line.split()[1:]  # Skip 'f'
                        face_vertices = []
                        for part in parts:
                            try:
                                # Handle different face formats (v, v/vt, v/vt/vn, v//vn)
                                vertex_index = int(part.split('/')[0]) - 1  # OBJ indices start at 1
                                if vertex_index >= 0 and vertex_index < len(vertices):
                                    face_vertices.append(vertex_index)
                            except (ValueError, IndexError):
                                continue
                        if len(face_vertices) >= 3:  # Valid face needs at least 3 vertices
                            faces.append(face_vertices)
        except Exception as e:
            print(f"Error parsing {obj_path}: {e}")
            return [], []
        
        print(f"  - Parsed {len(vertices)} vertices and {len(faces)} faces")
        return vertices, faces
    
    def calculate_ground_area(self, vertices, faces):
        """Calculate 2D ground area of the building"""
        if not vertices or not faces:
            return 0.0
        
        # Find the minimum Z coordinate (ground level)
        min_z = min(vertex[2] for vertex in vertices)
        tolerance = 0.1  # Small tolerance for floating point comparison
        
        # Get vertices that are at or near ground level
        ground_vertices = []
        for vertex in vertices:
            if abs(vertex[2] - min_z) <= tolerance:
                ground_vertices.append((vertex[0], vertex[1]))  # Only X, Y coordinates
        
        if len(ground_vertices) < 3:
            return 0.0
        
        # Create a polygon from ground vertices and calculate area
        try:
            # Remove duplicates while preserving order
            unique_ground_vertices = []
            for vertex in ground_vertices:
                if vertex not in unique_ground_vertices:
                    unique_ground_vertices.append(vertex)
            
            if len(unique_ground_vertices) >= 3:
                polygon = Polygon(unique_ground_vertices)
                return abs(polygon.area)  # Ensure positive area
        except Exception as e:
            print(f"    Warning: Error calculating ground area: {e}")
        
        return 0.0
    
    def calculate_building_height(self, vertices):
        """Calculate building height (max Z - min Z)"""
        if not vertices:
            return 0.0
        
        z_coords = [vertex[2] for vertex in vertices]
        height = max(z_coords) - min(z_coords)
        return abs(height)  # Ensure positive height
    
    def calculate_centroid(self, vertices):
        """Calculate centroid of the building"""
        if not vertices:
            return 0.0, 0.0
        
        x_coords = [vertex[0] for vertex in vertices]
        y_coords = [vertex[1] for vertex in vertices]
        
        centroid_x = sum(x_coords) / len(x_coords)
        centroid_y = sum(y_coords) / len(y_coords)
        
        return centroid_x, centroid_y
    
    def find_overlapping_admin(self, centroid_x, centroid_y):
        """Find administrative area that contains the building centroid"""
        point = Point(centroid_x, centroid_y)
        
        # Check which polygon contains this point
        for idx, row in self.gdf.iterrows():
            try:
                if row.geometry and row.geometry.contains(point):
                    return {
                        'kelurahan': row['WADMKD'] if pd.notna(row['WADMKD']) else 'UNKNOWN',
                        'kecamatan': row['WADMKC'] if pd.notna(row['WADMKC']) else 'UNKNOWN',
                        'kota': row['WADMKK'] if pd.notna(row['WADMKK']) else 'UNKNOWN'
                    }
            except Exception:
                continue
        
        # If no exact match, find the closest one
        min_distance = float('inf')
        closest_admin = None
        
        for idx, row in self.gdf.iterrows():
            try:
                if row.geometry:
                    distance = point.distance(row.geometry)
                    if distance < min_distance:
                        min_distance = distance
                        closest_admin = {
                            'kelurahan': row['WADMKD'] if pd.notna(row['WADMKD']) else 'UNKNOWN',
                            'kecamatan': row['WADMKC'] if pd.notna(row['WADMKC']) else 'UNKNOWN',
                            'kota': row['WADMKK'] if pd.notna(row['WADMKK']) else 'UNKNOWN'
                        }
            except Exception:
                continue
        
        return closest_admin or {'kelurahan': 'UNKNOWN', 'kecamatan': 'UNKNOWN', 'kota': 'UNKNOWN'}
    
    def generate_nib(self, kota, kecamatan, centroid_x, centroid_y):
        """Generate 14-digit NIB"""
        kota_code = self.kota_codes.get(kota, "00")
        kecamatan_code = self.kecamatan_codes.get(kecamatan, "00")
        
        # Get last 5 digits of X and Y coordinates (no decimals)
        x_str = str(int(abs(centroid_x)))[-5:].zfill(5)
        y_str = str(int(abs(centroid_y)))[-5:].zfill(5)
        
        nib = kota_code + kecamatan_code + x_str + y_str
        return nib
    
    def generate_nop(self, kota, kecamatan, kelurahan, centroid_x, centroid_y):
        """Generate 18-digit NOP and format it"""
        kota_code = self.kota_codes.get(kota, "00")
        kecamatan_code = self.kecamatan_codes.get(kecamatan, "00")
        kelurahan_code = self.kelurahan_codes.get(kelurahan, "000")
        
        # Get coordinates as integers (no decimals)
        x_int = str(int(abs(centroid_x)))
        y_int = str(int(abs(centroid_y)))
        
        # Combine coordinates and take appropriate length to make total 18 digits
        coord_str = x_int + y_int
        remaining_digits = 18 - 2 - 2 - 3  # 11 digits remaining
        coord_part = coord_str[:remaining_digits].ljust(remaining_digits, '0')
        
        nop_digits = kota_code + kecamatan_code + kelurahan_code + coord_part
        
        # Format the NOP using the format_nop function
        formatted_nop = self.format_nop(nop_digits)
        return formatted_nop
    
    def process_obj_file(self, obj_path):
        """Process a single OBJ file and return CSV row data"""
        filename = Path(obj_path).stem  # Filename without extension
        print(f"Processing: {filename}")
        
        # Parse OBJ file
        vertices, faces = self.parse_obj_file(obj_path)
        
        if not vertices:
            print(f"  Warning: No vertices found in {obj_path}")
            return None
        
        # Calculate metrics
        ground_area = self.calculate_ground_area(vertices, faces)
        building_height = self.calculate_building_height(vertices)
        centroid_x, centroid_y = self.calculate_centroid(vertices)
        
        print(f"  - Ground area: {ground_area:.2f} m²")
        print(f"  - Building height: {building_height:.2f} m")
        print(f"  - Centroid: ({centroid_x:.2f}, {centroid_y:.2f})")
        
        # Calculate number of floors
        jumlah_lantai = max(1, int(building_height / 5))  # Minimum 1 floor
        
        # Find administrative area
        admin_info = self.find_overlapping_admin(centroid_x, centroid_y)
        print(f"  - Administrative area: {admin_info}")
        
        # Generate random Indonesian name
        owner_name = self.generate_indonesian_name()
        print(f"  - Generated owner name: {owner_name}")
        
        # Generate NIB and NOP
        nib = self.generate_nib(admin_info['kota'], admin_info['kecamatan'], centroid_x, centroid_y)
        nop = self.generate_nop(admin_info['kota'], admin_info['kecamatan'], 
                               admin_info['kelurahan'], centroid_x, centroid_y)
        
        print(f"  - NIB: {nib}")
        print(f"  - NOP: {nop}")
        
        return {
            'uuid': filename,
            'ownerName': owner_name,
            'village': admin_info['kelurahan'],
            'district': admin_info['kecamatan'],
            'city': admin_info['kota'],
            'province': "DKJ",
            'buildingArea': round(ground_area, 2),
            'buildingHeight': round(building_height, 2),
            'floorCount': jumlah_lantai,
            'nib': nib,
            'nop': nop
        }
    
    def generate_csv_for_all_obj(self):
        """Generate CSV file for all OBJ files in the folder"""
        obj_files = list(Path(self.obj_folder_path).glob("*.obj"))
        
        if not obj_files:
            print(f"No OBJ files found in {self.obj_folder_path}")
            return
        
        print(f"\nFound {len(obj_files)} OBJ files")
        print("=" * 50)
        
        # Process each OBJ file
        all_data = []
        successful_count = 0
        
        for i, obj_file in enumerate(obj_files, 1):
            print(f"\n[{i}/{len(obj_files)}] Processing {obj_file.name}...")
            try:
                row_data = self.process_obj_file(obj_file)
                if row_data:
                    all_data.append(row_data)
                    successful_count += 1
                    print(f"  ✓ Successfully processed")
                else:
                    print(f"  ✗ Failed to process")
            except Exception as e:
                print(f"  ✗ Error processing {obj_file.name}: {e}")
        
        # Write to CSV
        if all_data:
            csv_filename = os.path.join(self.output_folder_path, "buildings_data.csv")
            
            # Updated fieldnames to match the new column structure
            fieldnames = ['uuid', 'ownerName', 'village', 'district', 'city', 'province',
                         'buildingArea', 'buildingHeight', 'floorCount', 'nib', 'nop']
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_data)
            
            print("\n" + "=" * 50)
            print("PROCESSING COMPLETE")
            print("=" * 50)
            print(f"CSV file generated: {csv_filename}")
            print(f"Total OBJ files found: {len(obj_files)}")
            print(f"Successfully processed: {successful_count}")
            print(f"Failed to process: {len(obj_files) - successful_count}")
            print(f"Records in CSV: {len(all_data)}")
            
            # Show sample of generated data
            if all_data:
                print(f"\nSample record:")
                sample = all_data[0]
                for key, value in sample.items():
                    print(f"  {key}: {value}")
        else:
            print("\n" + "=" * 50)
            print("ERROR: No valid data to write to CSV")
            print("Please check your OBJ files and try again.")

def main():
    parser = argparse.ArgumentParser(
        description='Generate CSV files from OBJ files with administrative boundary data and Indonesian names',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python attribute_gen.py --geojson data.geojson --obj_dir ./objects --output ./results
  python attribute_gen.py --geojson "Kelurahan DKI.geojson" --obj_dir "C:/models" --output "C:/output"

Features:
  - Random Indonesian owner names (2-3 words)
  - Formatted NOP: XX.XX.XXX.XXX.XXX-XXXX.X
  - Updated column names (uuid, ownerName, village, district, city, buildingArea, buildingHeight, floorCount, nib, nop)
        """
    )
    
    parser.add_argument(
        '--geojson',
        required=True,
        help='Path to the GeoJSON file containing administrative boundaries'
    )
    
    parser.add_argument(
        '--obj_dir',
        required=True,
        help='Directory containing OBJ files to process'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        help='Output directory for generated CSV files'
    )
    
    args = parser.parse_args()
    
    # Validate input files/directories
    if not os.path.exists(args.geojson):
        print(f"Error: GeoJSON file not found: {args.geojson}")
        return 1
    
    if not os.path.exists(args.obj_dir):
        print(f"Error: OBJ directory not found: {args.obj_dir}")
        return 1
    
    if not os.path.isdir(args.obj_dir):
        print(f"Error: OBJ path is not a directory: {args.obj_dir}")
        return 1
    
    print("OBJ to CSV Generator with Indonesian Names")
    print("=" * 50)
    print(f"GeoJSON file: {args.geojson}")
    print(f"OBJ directory: {args.obj_dir}")
    print(f"Output directory: {args.output}")
    print("=" * 50)
    
    try:
        # Create generator instance
        generator = OBJToCSVGenerator(args.geojson, args.obj_dir, args.output)
        
        # Generate CSV for all OBJ files
        generator.generate_csv_for_all_obj()
        
        return 0
    
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    import pandas as pd  # Add pandas import for notna function
    
    sys.exit(main())
