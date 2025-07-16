import numpy as np
from pyproj import Transformer
import os

def transform_obj_coordinates(input_obj, output_obj, local_reference, utm_reference):
    # Calculate translation vector
    translation_vector = np.array(utm_reference) - np.array(local_reference)

    # Open input and output files
    with open(input_obj, 'r') as infile, open(output_obj, 'w') as outfile:
        for line in infile:
            if line.startswith('v '):  # Only process vertex lines
                parts = line.split()
                x_local, y_local, z_local = map(float, parts[1:4])
                
                # Apply translation
                x_utm = x_local + translation_vector[0]
                y_utm = y_local + translation_vector[1]
                z_utm = z_local + translation_vector[2]
                
                # Write transformed vertex
                outfile.write(f"v {x_utm} {y_utm} {z_utm}\n")
            else:
                # Copy other lines directly
                outfile.write(line)
    print(f"Transformed OBJ file saved to: {output_obj}")

transform_obj_coordinates("leger/coba.obj", "leger/coba_translated.obj", (0,0,0), (428501.44556600949727, 9137577.566948587074876, 100.559806823730469))