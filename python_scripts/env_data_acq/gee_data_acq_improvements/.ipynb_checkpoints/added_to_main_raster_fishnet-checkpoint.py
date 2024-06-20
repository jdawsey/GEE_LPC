import geopandas as gpd
from shapely.geometry import box
import numpy as np
import os
import rasterio
from rasterio.windows import from_bounds


class RasterFishnet:
    def __init__(self, raster_path, max_pixels_per_cell, output_folder, tif_name, crs="EPSG:4326"):
        self.raster_path = raster_path
        self.max_pixels_per_cell = max_pixels_per_cell
        self.output_folder = output_folder
        self.crs = crs
        self.tif_name = tif_name
        
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
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

    
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

    
    def extract_subrasters(self):
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
                
                output_path = os.path.join(self.output_folder, f'{self.tif_name}_cell_{cell_num}.tif')
                with rasterio.open(output_path, 'w', **meta) as dest:
                    dest.write(sub_raster)

                print(f"Extracted sub-raster for cell {idx}")