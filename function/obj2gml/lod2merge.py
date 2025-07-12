#!/usr/bin/env python3
"""
CityGML File Merger
Merges multiple CityGML files from a directory into a single CityGML file.
Preserves all original information including headers, SRS, metadata, geometry, and attributes.

Author: Digital Twin UGM
Date: 2025-05-26
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import argparse
import re

import geopandas as gpd
from shapely.geometry import shape, Point
from shapely.wkt import loads as wkt_loads


class CityGMLMerger:
    def __init__(self):
        # Define CityGML namespaces
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'core': 'http://www.opengis.net/citygml/2.0',
            'bldg': 'http://www.opengis.net/citygml/building/2.0',
            'app': 'http://www.opengis.net/citygml/appearance/2.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0',
            'grp': 'http://www.opengis.net/citygml/cityobjectgroup/2.0',
            'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        
        # Register namespaces for ElementTree
        for prefix, uri in self.namespaces.items():
            ET.register_namespace(prefix, uri)

    def get_citygml_files(self, directory_path):
        """
        Get all CityGML files from the specified directory.
        
        Args:
            directory_path (str): Path to directory containing CityGML files
            
        Returns:
            list: List of CityGML file paths
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Look for .gml and .xml files
        gml_files = list(directory.glob("*.gml")) + list(directory.glob("*.xml"))
        
        if not gml_files:
            raise ValueError(f"No CityGML files found in directory: {directory_path}")
        
        return sorted(gml_files)

    def validate_citygml_file(self, file_path):
        """
        Validate if the file is a valid CityGML file.
        
        Args:
            file_path (Path): Path to the file to validate
            
        Returns:
            bool: True if valid CityGML file, False otherwise
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Check if root element is CityModel
            if root.tag.endswith('CityModel'):
                return True
            return False
        except ET.ParseError as e:
            print(f"Warning: XML parsing error in {file_path}: {e}")
            return False
        except Exception as e:
            print(f"Warning: Error validating {file_path}: {e}")
            return False

    def calculate_merged_bounds(self, bounds_list):
        """
        Calculate the merged bounding box from multiple bounding boxes.
        
        Args:
            bounds_list (list): List of bounding box dictionaries
            
        Returns:
            dict: Merged bounding box with lower and upper corners
        """
        if not bounds_list:
            return None
        
        # Initialize with first bounds
        merged = {
            'lower_x': bounds_list[0]['lower_x'],
            'lower_y': bounds_list[0]['lower_y'],
            'lower_z': bounds_list[0]['lower_z'],
            'upper_x': bounds_list[0]['upper_x'],
            'upper_y': bounds_list[0]['upper_y'],
            'upper_z': bounds_list[0]['upper_z'],
            'srs': bounds_list[0]['srs']
        }
        
        # Merge with other bounds
        for bounds in bounds_list[1:]:
            merged['lower_x'] = min(merged['lower_x'], bounds['lower_x'])
            merged['lower_y'] = min(merged['lower_y'], bounds['lower_y'])
            merged['lower_z'] = min(merged['lower_z'], bounds['lower_z'])
            merged['upper_x'] = max(merged['upper_x'], bounds['upper_x'])
            merged['upper_y'] = max(merged['upper_y'], bounds['upper_y'])
            merged['upper_z'] = max(merged['upper_z'], bounds['upper_z'])
        
        return merged

    def extract_bounds(self, root):
        """
        Extract bounding box information from CityGML root element.
        
        Args:
            root: XML root element
            
        Returns:
            dict: Bounding box information
        """
        try:
            # Find boundedBy element
            bounded_by = root.find('.//{http://www.opengis.net/gml}boundedBy')
            if bounded_by is None:
                return None
            
            envelope = bounded_by.find('.//{http://www.opengis.net/gml}Envelope')
            if envelope is None:
                return None
            
            lower_corner = envelope.find('.//{http://www.opengis.net/gml}lowerCorner')
            upper_corner = envelope.find('.//{http://www.opengis.net/gml}upperCorner')
            
            if lower_corner is None or upper_corner is None:
                return None
            
            # Parse coordinates
            lower_coords = lower_corner.text.strip().split()
            upper_coords = upper_corner.text.strip().split()
            
            return {
                'lower_x': float(lower_coords[0]),
                'lower_y': float(lower_coords[1]),
                'lower_z': float(lower_coords[2]),
                'upper_x': float(upper_coords[0]),
                'upper_y': float(upper_coords[1]),
                'upper_z': float(upper_coords[2]),
                'srs': envelope.get('srsName', ''),
                'srs_dimension': envelope.get('srsDimension', '3')
            }
        except (ValueError, IndexError) as e:
            print(f"Warning: Error parsing bounds: {e}")
            return None

    def extract_root_attributes(self, file_paths):
        """
        Extract root attributes from the first valid CityGML file to use as template.
        
        Args:
            file_paths (list): List of CityGML file paths
            
        Returns:
            dict: Root element attributes
        """
        for file_path in file_paths:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                # Return the attributes from the first valid file
                return dict(root.attrib)
            except Exception as e:
                print(f"Warning: Could not extract attributes from {file_path}: {e}")
                continue
        
        # Fallback: return minimal required attributes
        return {
            '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 
                'http://www.opengis.net/citygml/2.0 http://schemas.opengis.net/citygml/2.0/cityGMLBase.xsd '
                'http://www.opengis.net/citygml/appearance/2.0 http://schemas.opengis.net/citygml/appearance/2.0/appearance.xsd '
                'http://www.opengis.net/citygml/building/2.0 http://schemas.opengis.net/citygml/building/2.0/building.xsd '
                'http://www.opengis.net/citygml/generics/2.0 http://schemas.opengis.net/citygml/generics/2.0/generics.xsd'
        }

    def update_ids_with_prefix(self, element, prefix):
        """
        Recursively update all gml:id attributes that start with 'UUID_' to use custom prefix.
        
        Args:
            element: XML element to process
            prefix (str): New prefix to replace 'UUID_'
        """
        # Update gml:id attribute if it exists and starts with 'UUID_'
        gml_id = element.get('{http://www.opengis.net/gml}id')
        if gml_id and gml_id.startswith('UUID_'):
            new_id = gml_id.replace('UUID_', f'{prefix}_', 1)
            element.set('{http://www.opengis.net/gml}id', new_id)
            print(f"  Updated ID: {gml_id} -> {new_id}")
        
        # Also check for regular 'id' attribute (fallback)
        regular_id = element.get('id')
        if regular_id and regular_id.startswith('UUID_'):
            new_id = regular_id.replace('UUID_', f'{prefix}_', 1)
            element.set('id', new_id)
            print(f"  Updated ID: {regular_id} -> {new_id}")
        
        # Recursively process all child elements
        for child in element:
            self.update_ids_with_prefix(child, prefix)

    def update_id_references(self, element, prefix):
        """
        Update any references to IDs that were changed (like xlink:href attributes).
        
        Args:
            element: XML element to process
            prefix (str): Prefix used for ID replacement
        """
        # Check xlink:href attributes
        xlink_href = element.get('{http://www.w3.org/1999/xlink}href')
        if xlink_href and xlink_href.startswith('#UUID_'):
            new_href = xlink_href.replace('#UUID_', f'#{prefix}_', 1)
            element.set('{http://www.w3.org/1999/xlink}href', new_href)
            print(f"  Updated reference: {xlink_href} -> {new_href}")
        
        # Check other potential reference attributes
        for attr_name, attr_value in element.attrib.items():
            if isinstance(attr_value, str) and attr_value.startswith('UUID_'):
                new_value = attr_value.replace('UUID_', f'{prefix}_', 1)
                element.set(attr_name, new_value)
                print(f"  Updated attribute {attr_name}: {attr_value} -> {new_value}")
        
        # Recursively process all child elements
        for child in element:
            self.update_id_references(child, prefix)

    def update_descriptions(self, element, author_name="Digital Twin UGM"):
        """
        Recursively update all gml:description elements that contain "created by converter".
        
        Args:
            element: XML element to process
            author_name (str): Name to replace "converter" with
        """
        # Check if this is a gml:description element
        if element.tag == f'{{{self.namespaces["gml"]}}}description':
            if element.text and 'created by converter' in element.text:
                old_text = element.text
                new_text = element.text.replace('created by converter', f'created by {author_name}')
                element.text = new_text
                print(f"  Updated description: '{old_text}' -> '{new_text}'")
        
        # Recursively process all child elements
        for child in element:
            self.update_descriptions(child, author_name)

    def create_merged_citygml(self, file_paths, uuid_map, output_name="Merged_CityModel", author_name="Digital Twin UGM"):
        """
        Create a merged CityGML document from multiple files and assign gml:id from UUIDs via spatial matching.
        
        Args:
            file_paths (list): List of CityGML file paths
            uuid_map (dict): Dictionary mapping GeoJSON centroid WKT -> UUID string
            output_name (str): Name for the merged city model (also used as ID prefix), also as fallback name/prefix for buildings without UUID
            author_name (str): Author name to replace "converter" in descriptions
            
        Returns:
            ET.ElementTree: Merged CityGML document
        """
        # Extract root attributes from first file to preserve original namespace declarations
        root_attribs = self.extract_root_attributes(file_paths)
        
        # Create root element with preserved attributes
        merged_root = ET.Element(f"{{{self.namespaces['core']}}}CityModel", root_attribs)
        
        # Add name element
        name_elem = ET.SubElement(merged_root, f"{{{self.namespaces['gml']}}}name")
        name_elem.text = output_name
        
        # Collect all bounds and city objects
        all_bounds = []
        # city_objects = []
        merged_members = []
        
        print(f"Processing {len(file_paths)} CityGML files...")
        
        for i, file_path in enumerate(file_paths, 1):
            print(f"Processing file {i}/{len(file_paths)}: {file_path.name}")
            
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                # Extract bounds
                bounds = self.extract_bounds(root)
                if bounds:
                    all_bounds.append(bounds)
                
                # Extract all cityObjectMember elements
                for member in root.findall('.//core:cityObjectMember', self.namespaces):
                    building = member.find('.//bldg:Building', self.namespaces)
                    if building is None:
                        continue

                # for city_object in root.findall(f".//{{{self.namespaces['core']}}}cityObjectMember"):
                    # Create a copy of the city object to avoid modifying the original
                    # city_object_copy = ET.fromstring(ET.tostring(city_object))
                    member_copy = ET.fromstring(ET.tostring(member))

                    # Re-locate building element in copied tree
                    building_copy = member_copy.find('.//bldg:Building', self.namespaces)
                    
                    # Estimate building centroid from posList
                    positions = building_copy.findall('.//gml:pos', self.namespaces)
                    coords = []
                    for pos in positions:
                        parts = list(map(float, pos.text.strip().split()))
                        if len(parts) >= 2:
                            coords.append(parts[:2])  # Take X, Y only

                    if len(coords) < 3:
                        print("  → Skipping: not enough coordinates")
                        continue

                    xs, ys = zip(*coords)
                    centroid = Point(sum(xs) / len(xs), sum(ys) / len(ys))

                    if uuid_map:
                        uuid = self.find_nearest_uuid(centroid, uuid_map)
                    else:
                        uuid = None

                    if uuid:
                        self.update_ids_with_uuid(building_copy, uuid)
                        self.update_references(building_copy, uuid)
                        print(f"  → Assigned UUID: {uuid}")
                    else:
                        # Update IDs with custom prefix
                        # print(f"  Updating IDs in {file_path.name}...")
                        # self.update_ids_with_prefix(city_object_copy, output_name)
                        # self.update_id_references(city_object_copy, output_name)
                        print(f"  → No UUID match found, using fallback prefix '{output_name}_'")
                        self.update_ids_with_prefix(building_copy, output_name)
                        self.update_id_references(building_copy, output_name)
                    
                    # Update descriptions
                    print(f"  Updating descriptions in {file_path.name}...")
                    # self.update_descriptions(city_object_copy, author_name)                    
                    # city_objects.append(city_object_copy)
                    self.update_descriptions(building_copy, author_name)
                    merged_members.append(member_copy)
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        # Calculate merged bounds
        if all_bounds:
            merged_bounds = self.calculate_merged_bounds(all_bounds)
            
            # Create boundedBy element
            bounded_by = ET.SubElement(merged_root, f"{{{self.namespaces['gml']}}}boundedBy")
            envelope = ET.SubElement(bounded_by, f"{{{self.namespaces['gml']}}}Envelope")
            envelope.set('srsName', merged_bounds['srs'])
            envelope.set('srsDimension', '3')
            
            lower_corner = ET.SubElement(envelope, f"{{{self.namespaces['gml']}}}lowerCorner")
            lower_corner.text = f"{merged_bounds['lower_x']} {merged_bounds['lower_y']} {merged_bounds['lower_z']}"
            
            upper_corner = ET.SubElement(envelope, f"{{{self.namespaces['gml']}}}upperCorner")
            upper_corner.text = f"{merged_bounds['upper_x']} {merged_bounds['upper_y']} {merged_bounds['upper_z']}"
        
        # Add all city objects to merged model
        # for city_object in city_objects:
        #     merged_root.append(city_object)
        for member in merged_members:
            merged_root.append(member)
        
        # print(f"Successfully merged {len(city_objects)} city objects from {len(file_paths)} files.")
        print(f"Successfully merged {len(merged_members)} city objects from {len(file_paths)} files.")
        print(f"All UUID_ prefixes have been replaced with '{output_name}_'")
        print(f"All descriptions updated to use author name: '{author_name}'")
        
        return ET.ElementTree(merged_root)

    def merge_files(self, input_directory, output_file, uuid_map, output_name="Merged_CityModel", author_name="Digital Twin UGM"):
        """
        Main method to merge CityGML files from a directory.
        
        Args:
            input_directory (str): Path to directory containing CityGML files
            output_file (str): Path for output merged file
            output_name (str): Name for the merged city model (also used as ID prefix)
            author_name (str): Author name to replace "converter" in descriptions
        """
        try:
            # Get all CityGML files
            file_paths = self.get_citygml_files(input_directory)
            print(f"Found {len(file_paths)} potential CityGML files.")
            
            # Validate files
            valid_files = []
            for file_path in file_paths:
                if self.validate_citygml_file(file_path):
                    valid_files.append(file_path)
                else:
                    print(f"Skipping invalid CityGML file: {file_path}")
            
            if not valid_files:
                raise ValueError("No valid CityGML files found in the directory.")
            
            print(f"Processing {len(valid_files)} valid CityGML files.")
            print(f"Will replace 'UUID_' prefix with '{output_name}_' in all IDs.")
            print(f"Will replace 'created by converter' with 'created by {author_name}' in descriptions.")
            
            # Create merged CityGML
            merged_tree = self.create_merged_citygml(valid_files, uuid_map, output_name, author_name)
            
            # Write output file
            merged_tree.write(
                output_file,
                encoding='UTF-8',
                xml_declaration=True,
                method='xml'
            )
            
            # Add comment header
            self.add_header_comment(output_file)
            
            print(f"Successfully created merged CityGML file: {output_file}")
            
        except Exception as e:
            print(f"Error during merging process: {e}")
            sys.exit(1)

    def add_header_comment(self, output_file):
        """
        Add header comment to the output file.
        
        Args:
            output_file (str): Path to output file
        """
        try:
            # Read the file
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create header comment
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            header_comment = f"""<?xml version="1.0" encoding="UTF-8"?>
            <!-- Merged CityGML File -->
            <!-- Generated by CityGML Merger on {timestamp} -->
            <!-- Original files merged into single CityGML document -->
            <!-- UUID_ prefixes replaced with custom prefix -->
            <!-- Descriptions updated with custom author name -->
            """
            
            # Replace the XML declaration with our header
            content = content.replace('<?xml version="1.0" encoding="UTF-8"?>', header_comment, 1)
            
            # Write back to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except Exception as e:
            print(f"Warning: Could not add header comment: {e}")
    
    # Function to load UUID mapping from a building outline GeoJSON file
    def load_uuid_mapping(self, bo_path):
        gdf = gpd.read_file(bo_path)
        
        if "UUID" not in gdf.columns:
            print("⚠️  UUID field not found in Building Outline File. Falling back to ID prefix.")
            return None  # <- will be handled later

        uuid_map = {}
        for _, row in gdf.iterrows():
            centroid = row.geometry.centroid
            uuid_map[centroid.wkt] = row['UUID']
        return uuid_map
    
    def find_nearest_uuid(self, building_centroid, uuid_map):
        min_dist = float('inf')
        best_uuid = None
        for wkt, uuid in uuid_map.items():
            geo_centroid = wkt_loads(wkt)
            dist = building_centroid.distance(geo_centroid)
            if dist < min_dist:
                min_dist = dist
                best_uuid = uuid
        return best_uuid

    def update_ids_with_uuid(self, element, uuid):
        gml_id = element.get('{http://www.opengis.net/gml}id')
        if gml_id and gml_id.startswith('UUID_'):
            element.set('{http://www.opengis.net/gml}id', uuid)

    def update_references(self, element, uuid):
        xlink_href = element.get('{http://www.w3.org/1999/xlink}href')
        if xlink_href and xlink_href.startswith('#UUID_'):
            element.set('{http://www.w3.org/1999/xlink}href', f'#{uuid}')

        for attr_name, attr_value in element.attrib.items():
            if isinstance(attr_value, str) and attr_value.startswith('UUID_'):
                element.set(attr_name, attr_value.replace('UUID_', f'{uuid}_'))

        for child in element:
            self.update_references(child, uuid)

def main():
    """Main function to handle command line arguments and execute merging."""
    parser = argparse.ArgumentParser(
        description='Merge multiple CityGML files into a single file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    Examples:
    python citygml_merger.py /path/to/citygml/files merged_output.gml
    python citygml_merger.py ./input_folder ./output/merged_city.gml --name "AG_09_C"
    python citygml_merger.py ./input_folder ./output/merged_city.gml --name "AG_09_C" --author "John Doe"
    
    The script will:
    1. Replace "UUID_" prefix in all building IDs with the --name parameter
    2. Replace "created by converter" with "created by [author]" in all descriptions
    
    Examples of changes:
    - UUID_d281adfc-4901-0f52-540b-48625 -> AG_09_C_d281adfc-4901-0f52-540b-48625
    - "10, created by converter" -> "10, created by Digital Twin UGM"
            """
    )
    
    parser.add_argument(
        'input_directory',
        help='Directory containing CityGML files to merge'
    )
    
    parser.add_argument(
        'output_file',
        help='Output path for merged CityGML file'
    )
    
    parser.add_argument(
        '--name',
        default='Merged_CityModel',
        help='Name for the merged city model and prefix for building IDs (default: Merged_CityModel)'
    )
    
    parser.add_argument(
        '--author',
        default='Digital Twin UGM',
        help='Author name to replace "converter" in descriptions (default: Digital Twin UGM)'
    )

    parser.add_argument('--bo', help='Building Outline GeoJSON file with UUID attributes')
    
    args = parser.parse_args()
    
    # Create merger instance and process files
    merger = CityGMLMerger()
    
    output_path = Path(args.output_file)
    output_name = Path(args.output_file).stem
    uuid_map = merger.load_uuid_mapping(args.bo) if args.bo else None

    merger.merge_files(args.input_directory, str(output_path), uuid_map, output_name, args.author)

if __name__ == "__main__":
    main()
