import os
import geopandas as gpd
from shapely.geometry import box, Point
import numpy as np
import pandas as pd
import fiona
import ee
import geemap
import time
import re
import rasterio
from rasterio.windows import from_bounds


### Exports band information from an ee.Image to each polygon that overlaps it. Pull on a 
### per-file basis. Should be used in tandem with PolygonFishnet class so that exported
### images do not contain more than the GEE extract limit (100,000,000 cells).
class ImageryDownload:
    def __init__(self, folder_directory, data_folder, image_stack, shp_dir):
        self.folder_directory = folder_directory
        self.data_folder = data_folder
        self.shp_dir = shp_dir
        self.shp_files = [f for f in os.listdir(self.shp_dir) if f.endswith('.shp')]
        self.image_stack = image_stack

    def process_shp_files(self, scale = "30"):
        count = 0
        # Iterate directory
        for path in os.listdir(self.shp_dir):
            # check if current path is a file
            if path.endswith('.shp'):
                count += 1
        print(f'Downloading data for {count} files')
        
        index_num = -1
        for shp_file in self.shp_files:
            regex_gcs = re.compile(r'[0-9]_gcs+')
            if (regex_gcs.search(shp_file) == None) == True:
                index_num = index_num + 1
                shp_path = os.path.join(self.shp_dir, shp_file)
                feature_collection = geemap.shp_to_ee(shp_path)
                feature = feature_collection.geometry()
                image_path = f'{self.folder_directory}/{self.data_folder}/cell_{index_num}_env_image.tif'
                geemap.ee_export_image(self.image_stack, image_path, scale, region = feature)
                print(f'Export task started for {shp_file}.')
                time.sleep(15)
            else:
                print("skipping gcs file")

        
        regex_gcs = re.compile(r'[0-9]_gcs+')
        delete_file_path = f'{self.shp_dir}/'
        delete_file_paths = os.listdir(delete_file_path)
        for file in delete_file_paths:
            full_path = f'{delete_file_path}{file}'
            if (regex_gcs.search(full_path) == None) == False:
                os.remove(full_path)
                print(f'removed {full_path}')



### ### At this point I'm not sure what this is useful for since it's simpler to
### export the GEE images of environmental data themselves. Might be good if plan
### to try using masked rasters rather than polygons.

### Creates a fishnet over the bounds of a raster. The number of pixels contained
### per cell can be specified. The original raster is then exported within the 
### bounds of each cell to a specified folder.
class RasterFishnet:
    def __init__(self, raster_path, max_pixels_per_cell, crs="EPSG:4326"):
        self.raster_path = raster_path
        self.max_pixels_per_cell = max_pixels_per_cell
        self.crs = crs
        
        # Load raster to get its metadata and bounds
        with rasterio.open(raster_path) as src:
            self.raster_meta = src.meta.copy()
            self.bounds = src.bounds
            self.pixel_size_x, self.pixel_size_y = src.res
        
        # Calculate cell size based on max pixels per cell
        self.cell_size_x = self.pixel_size_x * np.sqrt(max_pixels_per_cell)
        self.cell_size_y = self.pixel_size_y * np.sqrt(max_pixels_per_cell)
        
        # Create fishnet
        self.grid = self.create_fishnet(self.bounds, self.cell_size_x, self.cell_size_y)
        print(f"Initial grid created with {len(self.grid)} cells")
        
        # Ensure output folder exists
        #if not os.path.exists(output_folder):
        #    os.makedirs(output_folder)

    
    def create_fishnet(self, bounds, cell_size_x, cell_size_y):
        xmin, ymin, xmax, ymax = bounds
        rows = int(np.ceil((ymax - ymin) / cell_size_y))
        cols = int(np.ceil((xmax - xmin) / cell_size_x))
        x_left_origin = xmin
        x_right_origin = xmin + cell_size_x
        y_top_origin = ymax
        y_bottom_origin = ymax - cell_size_y

        polygons = []
        for i in range(cols):
            y_top = y_top_origin
            y_bottom = y_bottom_origin
            for j in range(rows):
                polygons.append(box(x_left_origin, y_bottom, x_right_origin, y_top))
                y_top = y_top - cell_size_y
                y_bottom = y_bottom - cell_size_y

            x_left_origin = x_left_origin + cell_size_x
            x_right_origin = x_right_origin + cell_size_x

        grid = gpd.GeoDataFrame({'geometry': polygons})
        grid.set_crs(self.crs, inplace=True)
        return grid

    
    def extract_subrasters(self, output_folder):
        cell_num = -1
        with rasterio.open(self.raster_path) as src:
            for idx, cell in self.grid.iterrows():
                cell_num += 1
                window = from_bounds(*cell.geometry.bounds, transform=src.transform)
                sub_raster = src.read(window=window)
                transform = src.window_transform(window)
                meta = src.meta.copy()
                meta.update({
                    "height": window.height,
                    "width": window.width,
                    "transform": transform
                })
                
                output_path = os.path.join(output_folder, f'cell_{cell_num}.tif')
                with rasterio.open(output_path, 'w', **meta) as dest:
                    dest.write(sub_raster)

                print(f"Extracted sub-raster for cell {idx}")