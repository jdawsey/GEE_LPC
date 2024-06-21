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



### Allows for the generation of an ee.Image containing n-bands specified by the user.
### It pulls the bands from a CSV file, renames them, and will resample them to the 
### desired resolution.
class ImageStackBuilder:
    def __init__(self, image_collections):
        self.image_collections = image_collections

    def build_image_stack(self, user_specified = None, rast_crs = 'EPSG:4326'):
        images = []
        
        if user_specified is None:
            for index in range(len(self.image_collections)):
                collection_loc = self.image_collections.loc[index, 'collection_loc']
                band_rename = self.image_collections.loc[index, 'band_rename']
                bands_rename_list = band_rename.split()
                image_bands = self.image_collections.loc[index, 'bands']
                image_band_list = image_bands.split()
                if self.image_collections.loc[index, 'resample'] == True:
                    asset_image = ee.Image(collection_loc)
                    resample_scale = int(self.image_collections.loc[index, 'resample_res'])
                    rasample_method = str(self.image_collections.loc[index, 'resample_method'])
                    #print("this is true")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.resample(resample_method).reproject(rast_crs, scale = resample_scale)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
                else:
                    asset_image = ee.Image(collection_loc)
                    #print("this is false")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]]).reproject(rast_crs)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
            return ee.Image(images)
            
        else:
            for index in range(len(self.image_collections)):
                collection_loc = self.image_collections.loc[index, 'collection_loc']
                band_rename = self.image_collections.loc[index, 'band_rename']
                bands_rename_list = band_rename.split()
                image_bands = self.image_collections.loc[index, 'bands']
                image_band_list = image_bands.split()
                if self.image_collections.loc[index, 'resample'] == True:
                    asset_image = ee.Image(collection_loc)
                    resample_scale = int(self.image_collections.loc[index, 'resample_res'])
                    resample_method = str(self.image_collections.loc[index, 'resample_method'])
                    #print("this is true")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.resample(resample_method).reproject(rast_crs, scale = resample_scale)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
                else:
                    asset_image = ee.Image(collection_loc)
                    #print("this is false")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]]).reproject(rast_crs)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)

            user_created_bands = ee.Image([user_specified])
            original_bands = ee.Image([images])
            merged_bands = original_bands.addBands(user_created_bands)
            return merged_bands



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



### Imports a file containing spatial polygon data and converts it to a geodataframe.
class PolyToGDF:
    def __init__(self, poly_path):
        self.poly_path = poly_path

    def poly_to_gdf(self, crs):
        poly_gdf = gpd.read_file(self.poly_path)
        poly_gdf.set_crs(crs, inplace = True)
        return poly_gdf
            


### Creates a fishnet over the bounds of a polygon (or polygons). The cell size and
### number of polygons per cell can be specified. The polygons contained in each 
### cell are exported as separate shapefiles to the specified folder.
class PolygonFishnet:
    def __init__(self, bounds, cell_size, crs="EPSG:4326", max_iterations=100):
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

    def count_polygons_in_cells(self, polygon_gdf):
        self.grid['polygons_count'] = self.grid.apply(
            lambda cell: polygon_gdf.intersects(cell.geometry).sum(),
            axis=1
        )
        self.grid = self.grid[self.grid['polygons_count'] > 0]
        #print(f"Counted polygons in cells, {len(self.grid)} cells contain polygons")

    def subdivide_cell(self, cell, polygon_gdf, max_polygons):
        if cell.polygons_count > max_polygons:
            xmin, ymin, xmax, ymax = cell.geometry.bounds
            new_cell_size = self.cell_size / 2

            sub_fishnet = PolygonFishnet((xmin, ymin, xmax, ymax), new_cell_size, self.crs, self.max_iterations - 1)
            sub_fishnet.count_polygons_in_cells(polygon_gdf)
            sub_fishnet.subdivide_high_density_cells(polygon_gdf, max_polygons)  # Recursive call

            return sub_fishnet.grid
        else:
            return gpd.GeoDataFrame([cell], crs=self.crs)

    def subdivide_high_density_cells(self, polygon_gdf, max_polygons):
        iteration = 0
        need_subdivision = True
        while need_subdivision and iteration < self.max_iterations:
            iteration += 1
            #print(f"Subdivision iteration {iteration}")
            subdivided_cells = gpd.GeoDataFrame(pd.concat([
                self.subdivide_cell(cell, polygon_gdf, max_polygons) for idx, cell in self.grid.iterrows()
            ], ignore_index=True))
            subdivided_cells.set_crs(self.crs, inplace=True)

            max_polygons_in_cell = subdivided_cells['polygons_count'].max()
            #print(f"After subdivision iteration {iteration}, {len(subdivided_cells)} cells created, max polygons in a cell: {max_polygons_in_cell}")
            if max_polygons_in_cell <= max_polygons:
                need_subdivision = False

            self.grid = subdivided_cells

    def export_polygons_in_cells(self, polygon_gdf, output_folder):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        for idx, cell in self.grid.iterrows():
            intersecting_polygons = polygon_gdf[polygon_gdf.intersects(cell.geometry)]
            if not intersecting_polygons.empty:
                file_path = os.path.join(output_folder, f'cell_{idx}.shp')
                intersecting_polygons.to_file(file_path)

    def export_fishnet_cells(self, output_folder):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        for idx, cell in self.grid.iterrows():
            cell_gdf = gpd.GeoDataFrame([cell], crs=self.crs)
            file_path = os.path.join(output_folder, f'fishnet_cell_{idx}.shp')
            cell_gdf.to_file(file_path)



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