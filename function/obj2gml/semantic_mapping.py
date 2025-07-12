"""
Building Colorizer - Version 2.0.0
Created: 2024
Description: Enhanced building colorizer with improved semantic classification
Features: Advanced ground detection, robust classification, and validation systems
"""

import os
import json
import numpy as np
import argparse
from pathlib import Path
import shapely.geometry as geometry
from shapely.geometry import Polygon
from datetime import datetime
from scipy import stats
from collections import defaultdict

__version__ = "2.0.0"

# Enhanced color definitions with alpha channel
COLORS = {
    'Roof': (1.0, 0.65, 0.0, 1.0),    # Orange
    'Wall': (0.5, 0.5, 0.5, 1.0),     # Grey
    'Ground': (0.82, 0.41, 0.12, 1.0)  # Chocolate
}

class MeshAnalyzer:
    """Handles mesh analysis and validation"""
    
    @staticmethod
    def analyze_z_distribution(z_values, bin_width=0.1):
        """
        Analyze Z-coordinate distribution to find ground level
        Uses histogram analysis to identify the most significant low-level plane
        """
        if not z_values:
            return 0.0
            
        # Create histogram of Z values
        hist, bin_edges = np.histogram(z_values, bins=50)
        
        # Find the lowest significant peak
        significant_threshold = max(hist) * 0.1
        for i, count in enumerate(hist):
            if count > significant_threshold:
                return bin_edges[i]
        
        return min(z_values)

    @staticmethod
    def get_face_centroid(vertices, face):
        """Calculate the centroid of a face"""
        face_vertices = [vertices[idx] for idx in face]
        return np.mean(face_vertices, axis=0)

    @staticmethod
    def get_face_area(vertices, face):
        """Calculate the area of a face"""
        if len(face) < 3:
            return 0.0
            
        v0 = vertices[face[0]]
        area = 0.0
        
        for i in range(1, len(face)-1):
            v1 = vertices[face[i]]
            v2 = vertices[face[i+1]]
            # Calculate area of triangle
            cross_product = np.cross(v1 - v0, v2 - v0)
            area += np.linalg.norm(cross_product) / 2
            
        return area

class GeometryValidator:
    """Handles geometric validation and consistency checks"""
    
    def __init__(self, tolerance=0.01):
        self.tolerance = tolerance
        
    def validate_ground_classification(self, vertices, face, ground_height):
        """
        Validate if a face should be classified as ground
        Returns True if the face meets ground criteria
        """
        face_z_coords = [vertices[idx][2] for idx in face]
        avg_z = sum(face_z_coords) / len(face_z_coords)
        
        # Check if face is at ground level
        if abs(avg_z - ground_height) > self.tolerance:
            return False
            
        # Check if face is horizontal
        normal = self.get_face_normal(vertices, face)
        return abs(normal[2]) > 0.95

    @staticmethod
    def get_face_normal(vertices, face):
        """Calculate normalized face normal"""
        if len(face) < 3:
            return np.array([0, 0, 1])
            
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]
        
        normal = np.cross(v1 - v0, v2 - v0)
        if np.all(normal == 0):
            return np.array([0, 0, 1])
        return normal / np.linalg.norm(normal)

class BuildingColorizer:
    def __init__(self, obj_dir, geojson_path):
        self.obj_dir = Path(obj_dir)
        self.geojson_path = Path(geojson_path)
        self.building_outlines = self.load_all_building_outlines()
        self.mesh_analyzer = MeshAnalyzer()
        self.geometry_validator = GeometryValidator()
        self.classification_cache = {}
        
        # Statistics and logging
        self.stats = {
            'processed_files': 0,
            'failed_files': [],
            'classification_changes': 0
        }
        self.start_time = datetime.now()

    def load_obj_file(self, obj_path):
        """
        Load vertices and faces from OBJ file
        Returns: tuple (vertices, faces)
        """
        vertices = []
        faces = []
        
        try:
            with open(obj_path, 'r') as f:
                for line in f:
                    if line.startswith('#'):  # Skip comments
                        continue
                        
                    values = line.split()
                    if not values:  # Skip empty lines
                        continue
                        
                    if values[0] == 'v':  # Vertex
                        try:
                            vertex = [float(values[1]), float(values[2]), float(values[3])]
                            vertices.append(vertex)
                        except (IndexError, ValueError) as e:
                            print(f"Warning: Invalid vertex in {obj_path.name}: {line.strip()}")
                            continue
                            
                    elif values[0] == 'f':  # Face
                        try:
                            # Handle different face formats (v, v/vt, v/vt/vn)
                            face = []
                            for v in values[1:]:
                                # Extract just the vertex index (before any '/')
                                vertex_idx = int(v.split('/')[0]) - 1  # OBJ indices start at 1
                                face.append(vertex_idx)
                            if len(face) >= 3:  # Only add faces with 3 or more vertices
                                faces.append(face)
                        except (IndexError, ValueError) as e:
                            print(f"Warning: Invalid face in {obj_path.name}: {line.strip()}")
                            continue
                            
            if not vertices or not faces:
                print(f"Warning: No valid vertices or faces found in {obj_path.name}")
                return None, None
                
            return np.array(vertices), faces
            
        except Exception as e:
            print(f"Error loading {obj_path.name}: {str(e)}")
            return None, None

    def load_all_building_outlines(self):
        """Enhanced building outline loader with validation"""
        building_outlines = {}
        try:
            with open(self.geojson_path, 'r') as f:
                data = json.load(f)
                for feature in data['features']:
                    if feature['geometry']['type'] in ['MultiPolygon', 'Polygon']:
                        coords = (feature['geometry']['coordinates'][0][0] 
                                if feature['geometry']['type'] == 'MultiPolygon'
                                else feature['geometry']['coordinates'][0])
                        try:
                            polygon = Polygon(coords)
                            if polygon.is_valid:
                                centroid = polygon.centroid
                                building_outlines[f"{centroid.x}_{centroid.y}"] = polygon
                        except Exception as e:
                            print(f"Invalid polygon: {str(e)}")
                            
            print(f"Loaded {len(building_outlines)} valid building outlines")
            return building_outlines
        except Exception as e:
            print(f"Error loading GeoJSON: {str(e)}")
            return {}

    def process_mesh(self, vertices, faces):
        """
        Process mesh data with enhanced analysis
        """
        # Find ground level using distribution analysis
        z_values = [v[2] for v in vertices]
        ground_height = self.mesh_analyzer.analyze_z_distribution(z_values)
        
        # Create spatial index for faces
        face_index = self.create_spatial_index(vertices, faces)
        
        # Process each face with context awareness
        classifications = []
        for face_idx, face in enumerate(faces):
            # Get neighboring faces
            neighbors = self.get_neighboring_faces(face_idx, face_index)
            
            # Classify face with context
            face_type = self.classify_face_with_context(
                vertices, face, ground_height, neighbors)
            
            classifications.append(face_type)
            
        return classifications, ground_height

    def classify_face_with_context(self, vertices, face, ground_height, neighbors):
        """
        Classify face considering neighboring geometry
        """
        # Get face properties
        normal = self.geometry_validator.get_face_normal(vertices, face)
        centroid = self.mesh_analyzer.get_face_centroid(vertices, face)
        
        # Basic classification
        if self.geometry_validator.validate_ground_classification(vertices, face, ground_height):
            base_class = 'Ground'
        elif abs(normal[2]) < 0.1:  # Nearly vertical
            base_class = 'Wall'
        else:
            base_class = 'Roof'
            
        # Consider neighbor consistency
        if neighbors:
            neighbor_classes = [self.classification_cache.get(n, base_class) for n in neighbors]
            most_common = max(set(neighbor_classes), key=neighbor_classes.count)
            
            # Only override if significantly different
            if most_common != base_class and neighbor_classes.count(most_common) > len(neighbors) * 0.7:
                self.stats['classification_changes'] += 1
                return most_common
                
        return base_class

    def create_spatial_index(self, vertices, faces):
        """
        Create spatial index for efficient neighbor queries
        """
        face_index = defaultdict(list)
        for i, face in enumerate(faces):
            centroid = self.mesh_analyzer.get_face_centroid(vertices, face)
            # Create grid cell key
            cell_key = tuple(np.floor(centroid / 0.5).astype(int))
            face_index[cell_key].append(i)
        return face_index

    def get_neighboring_faces(self, face_idx, face_index):
        """
        Find neighboring faces using spatial index
        """
        # Implementation depends on spatial index structure
        # This is a simplified version
        return []  # TODO: Implement proper neighbor finding

    def create_materials(self, obj_path, classifications):
        """
        Create enhanced material definitions
        """
        mtl_path = obj_path.with_suffix('.mtl')
        
        try:
            with open(mtl_path, 'w') as f:
                f.write("# Generated by Building Colorizer v2.0.0\n\n")
                
                for mat_name, color in COLORS.items():
                    f.write(f"newmtl {mat_name}\n")
                    f.write(f"Ka 0.000 0.000 0.000\n")
                    f.write(f"Kd {color[0]:.6f} {color[1]:.6f} {color[2]:.6f}\n")
                    f.write(f"Ks 0.000 0.000 0.000\n")
                    f.write(f"d {color[3]:.6f}\n")
                    f.write("illum 1\n\n")
                    
        except Exception as e:
            self.stats['failed_files'].append((obj_path.name, f"Material creation failed: {str(e)}"))

    def update_obj_file(self, obj_path, classifications):
        """
        Update OBJ file with material assignments
        """
        temp_path = obj_path.with_suffix('.tmp')
        
        try:
            with open(obj_path, 'r') as src, open(temp_path, 'w') as dst:
                # Write header
                dst.write(f"# Processed by Building Colorizer v{__version__}\n")
                dst.write(f"mtllib {obj_path.stem}.mtl\n")
                
                face_idx = 0
                current_material = None
                
                for line in src:
                    if line.startswith('f '):
                        new_material = classifications[face_idx]
                        if new_material != current_material:
                            dst.write(f"usemtl {new_material}\n")
                            current_material = new_material
                        dst.write(line)
                        face_idx += 1
                    elif not line.startswith(('mtllib', 'usemtl')):
                        dst.write(line)
                        
            # Replace original file
            os.replace(temp_path, obj_path)
            
        except Exception as e:
            self.stats['failed_files'].append((obj_path.name, f"OBJ update failed: {str(e)}"))
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def process_building(self, obj_path):
        """
        Process a single building with enhanced logging
        """
        print(f"\nProcessing: {obj_path.name}")
        
        try:
            # Load mesh data
            print(f"  Loading mesh data...")
            vertices, faces = self.load_obj_file(obj_path)
            if vertices is None or faces is None:
                print(f"  Failed to load mesh data for {obj_path.name}")
                return
                
            print(f"  Loaded {len(vertices)} vertices and {len(faces)} faces")
            
            # Process mesh
            print(f"  Processing mesh...")
            classifications, ground_height = self.process_mesh(vertices, faces)
            print(f"  Ground height detected: {ground_height:.2f}")
            
            # Create materials and update OBJ
            print(f"  Creating materials...")
            self.create_materials(obj_path, classifications)
            
            print(f"  Updating OBJ file...")
            self.update_obj_file(obj_path, classifications)
            
            self.stats['processed_files'] += 1
            print(f"  Successfully processed {obj_path.name}")
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            print(f"  Error: {error_msg}")
            self.stats['failed_files'].append((obj_path.name, error_msg))

    def process_all_buildings(self):
        """
        Process all buildings in directory
        """
        for obj_path in self.obj_dir.glob('*.obj'):
            self.process_building(obj_path)
        self.print_summary()

    def print_summary(self):
        """
        Print detailed processing summary
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n=== Building Colorizer v2.0.0 Summary ===")
        print(f"Processing completed in {duration:.2f} seconds")
        print(f"Files processed: {self.stats['processed_files']}")
        print(f"Classification adjustments: {self.stats['classification_changes']}")
        print(f"Failed files: {len(self.stats['failed_files'])}")
        
        if self.stats['failed_files']:
            print("\nFailed files:")
            for name, error in self.stats['failed_files']:
                print(f"- {name}: {error}")
        print("=====================================")

def main():
    parser = argparse.ArgumentParser(description='Building Colorizer v2.0.0')
    parser.add_argument('--obj-dir', required=True, help='Directory containing OBJ files')
    parser.add_argument('--geojson', required=True, help='Path to GeoJSON building outlines')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    colorizer = BuildingColorizer(args.obj_dir, args.geojson)
    colorizer.process_all_buildings()

if __name__ == '__main__':
    main()
