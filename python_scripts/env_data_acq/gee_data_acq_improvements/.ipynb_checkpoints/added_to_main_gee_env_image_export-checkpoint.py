import geopandas as gpd
from shapely.geometry import box
import numpy as np
import os
import geemap
import ee
import re
import time


class PolyToGDF:
    def __init__(self, poly_path):
        #self.points_gdf = points_gdf
        self.poly_path = poly_path

    def poly_to_gdf(self, crs):
        poly_gdf = gpd.read_file(self.poly_path)
        poly_gdf.set_crs(crs, inplace = True)
        return poly_gdf

# Should fishnet the bounds of a polygon such that a raster image of scale "x" within \
# each fishnet cell will only contain a specified number of pixels within it.
class PolygonFishnet:
    def __init__(self, polygon_gdf, cell_size, output_folder, crs="EPSG:4326"):
        self.polygon_gdf = polygon_gdf
        self.cell_size = cell_size
        self.output_folder = output_folder
        self.crs = crs
        
        # Calculate bounds of the polygon
        self.bounds = polygon_gdf.total_bounds  # (xmin, ymin, xmax, ymax)
        
        # Create fishnet
        self.grid = self.create_fishnet(self.bounds, cell_size)
        print(f"Initial grid created with {len(self.grid)} cells")
        
        # Ensure output folder exists
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

    def create_fishnet(self, bounds, cell_size):
        xmin, ymin, xmax, ymax = bounds
        rows = int(np.ceil((ymax - ymin) / cell_size))
        cols = int(np.ceil((xmax - xmin) / cell_size))
        x_left_origin = xmin
        x_right_origin = xmin + cell_size
        y_top_origin = ymax
        y_bottom_origin = ymax - cell_size

        polygons = []
        for i in range(cols):
            y_top = y_top_origin
            y_bottom = y_bottom_origin
            for j in range(rows):
                polygons.append(box(x_left_origin, y_bottom, x_right_origin, y_top))
                y_top = y_top - cell_size
                y_bottom = y_bottom - cell_size

            x_left_origin = x_left_origin + cell_size
            x_right_origin = x_right_origin + cell_size

        grid = gpd.GeoDataFrame({'geometry': polygons})
        grid.set_crs(self.crs, inplace=True)
        return grid

    def intersect_and_export(self):
        cell_num = -1
        # Intersect the grid with the polygon
        intersected_gdf = gpd.overlay(self.grid, self.polygon_gdf, how='intersection')
        
        for idx, intersecting_part in intersected_gdf.iterrows():
            cell_num += 1
            intersecting_part_gdf = gpd.GeoDataFrame([intersecting_part], crs=self.crs)
            file_path = os.path.join(self.output_folder, f'cell_{cell_num}.shp')
            intersecting_part_gdf.to_file(file_path)
            print(f"Exported intersecting part {idx} to {file_path}")


class ImageryDownload:
    def __init__(self, folder_directory, data_folder, image_stack, shp_dir):
        self.folder_directory = folder_directory
        self.data_folder = data_folder
        self.shp_dir = shp_dir
        self.shp_files = [f for f in os.listdir(self.shp_dir) if f.endswith('.shp')]
        self.image_stack = image_stack

    def process_shp_files(self):
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
                geemap.ee_export_image(self.image_stack, image_path, scale = 30, region = feature)
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







