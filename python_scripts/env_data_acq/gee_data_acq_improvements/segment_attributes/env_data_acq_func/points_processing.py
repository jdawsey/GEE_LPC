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


### Imports a file containing spatial point data and converts it to a geodataframe.
class PointsToGDF:
    def __init__(self, points_path):
        #self.points_gdf = points_gdf
        self.points_path = points_path

    def points_to_gdf(self, crs):
        points_gdf = gpd.read_file(self.points_path)
        points_gdf.set_crs(crs, inplace = True)
        return points_gdf

    # Below is the old class method
    #def get_points_gdf(self):
    #    return self.points_gdf


### Creates a fishnet over the bounds of set of points. The cell size for the fishnet
### can be specified. Cells can then be automatically split if they contain more than
### a specified number of points. Finally the points from each cell are exported as
### separate shapefiles to a folder.
class PointFishnet:
    def __init__(self, bounds, cell_size, crs="EPSG:4326", max_iterations=10):
        self.bounds = bounds
        self.cell_size = cell_size
        self.crs = crs
        self.max_iterations = max_iterations
        self.grid = self.create_fishnet(bounds, cell_size)
        #print(f"Initial grid created with {len(self.grid)} cells")

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

    def count_points_in_cells(self, points_gdf):
        self.grid['points_count'] = self.grid.apply(
            lambda cell: points_gdf.within(cell.geometry).sum(),
            axis=1
        )
        self.grid = self.grid[self.grid['points_count'] > 0]
        #print(f"Counted points in cells, {len(self.grid)} cells contain points")

    def subdivide_cell(self, cell, points_gdf, max_points):
        if cell.points_count > max_points:
            xmin, ymin, xmax, ymax = cell.geometry.bounds
            new_cell_size = self.cell_size / 2

            sub_fishnet = Fishnet((xmin, ymin, xmax, ymax), new_cell_size, self.crs, self.max_iterations - 1)
            sub_fishnet.count_points_in_cells(points_gdf)
            sub_fishnet.subdivide_high_density_cells(points_gdf, max_points)  # Recursive call

            return sub_fishnet.grid
        else:
            return gpd.GeoDataFrame([cell], crs=self.crs)

    def subdivide_high_density_cells(self, points_gdf, max_points):
        iteration = 0
        need_subdivision = True
        while need_subdivision and iteration < self.max_iterations:
            iteration += 1
            subdivided_cells = gpd.GeoDataFrame(pd.concat([
                self.subdivide_cell(cell, points_gdf, max_points) for idx, cell in self.grid.iterrows()
            ], ignore_index=True))
            subdivided_cells.set_crs(self.crs, inplace=True)

            max_points_in_cell = subdivided_cells['points_count'].max()
            #print(f"After subdivision iteration {iteration}, {len(subdivided_cells)} cells created, max points in a cell: {max_points_in_cell}")
            if max_points_in_cell <= max_points:
                need_subdivision = False

            self.grid = subdivided_cells

    def export_points_in_cells(self, points_gdf, output_folder):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        cell_num = -1
        for idx, cell in self.grid.iterrows():
            cell_num += 1
            intersecting_points = points_gdf[points_gdf.within(cell.geometry)]
            intersection_points = intersecting_points.to_crs("EPSG:4326")
            if not intersecting_points.empty:
                file_path = f'{output_folder}/cell_{cell_num}.shp'
                intersecting_points.to_file(file_path, driver='ESRI Shapefile')




### Exports band information from an ee.Image to points. Pull points for extract on a
### per-file basis, allowing for the export of more than 5000 points at a time (so
### long as there aren't more than 5000 points in any one file).
class PointEnvData:
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
                out_csv = f'{self.folder_directory}/{self.data_folder}/cell_{index_num}_with_env_data.csv'
                geemap.extract_values_to_points(feature_collection, self.image_stack, out_csv)
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
