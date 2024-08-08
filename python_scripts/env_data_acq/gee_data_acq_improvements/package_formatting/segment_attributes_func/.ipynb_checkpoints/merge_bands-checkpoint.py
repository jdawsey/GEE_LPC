import os
import rasterio
from rasterio.merge import merge
import numpy as np

"""
Takes two folders, each containing image with bands wanting to be merged, and merges them by a common index. The specified output folder will contain the newly merged images.
"""
def merge_bands(folder1, folder2, output_folder):
    
    # Get list of raster files
    raster_files1 = sorted([f for f in os.listdir(folder1) if f.endswith('.tif')])
    raster_files2 = sorted([f for f in os.listdir(folder2) if f.endswith('.tif')])

    # Ensure both folders have the same number of files
    assert len(raster_files1) == len(raster_files2), "Folders do not contain the same number of rasters."

    # Function to add bands from one raster to another
    def add_bands(raster1_path, raster2_path, output_path):
        with rasterio.open(raster1_path) as src1:
            with rasterio.open(raster2_path) as src2:
                meta = src1.meta
                meta.update(count=src1.count + src2.count)
    
                # Create an empty array to store the new data
                new_data = np.zeros((meta['count'], meta['height'], meta['width']), dtype=src1.dtypes[0])
    
                # Read data from first raster
                for i in range(1, src1.count + 1):
                    new_data[i-1] = src1.read(i)
    
                # Read data from second raster
                for i in range(1, src2.count + 1):
                    new_data[src1.count + i-1] = src2.read(i)
    
                # Write the new raster
                with rasterio.open(output_path, 'w', **meta) as dst:
                    for i in range(1, meta['count'] + 1):
                        dst.write(new_data[i-1], i)
    
    # Process each pair of raster files
    for file1, file2 in zip(raster_files1, raster_files2):
        raster1_path = os.path.join(folder1, file1)
        raster2_path = os.path.join(folder2, file2)
        output_path = os.path.join(output_folder, file1)  # Save output with the same name as the first raster
    
        add_bands(raster1_path, raster2_path, output_path)
    
    print("Band addition completed.")