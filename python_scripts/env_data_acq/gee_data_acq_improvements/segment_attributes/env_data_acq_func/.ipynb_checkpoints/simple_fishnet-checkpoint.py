import geopandas as gpd
from shapely.geometry import box
import numpy as np
import pandas as pd
import os


"""
Class that creates an instance that can be used for exporting individual cells of a fishnet of a given cell size.
Takes the bounds of a geopandas dataframe, the user specified cell size (dependent upon the coordinate reference system), and the crs of the data.
export_fishnet_cells requires the directory of the folder to send the shapefiles to to be specified or else it will make it itself.
"""
class SimpleFishnet:
    def __init__(self, bounds, cell_size, crs="EPSG:4326"):
        self.bounds = bounds
        self.cell_size = cell_size
        self.crs = crs
        self.grid = self.create_fishnet(bounds, cell_size)
        print(f"Initial grid created with {len(self.grid)} cells")

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

    def export_fishnet_cells(self, output_folder):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        for idx, cell in self.grid.iterrows():
            cell_gdf = gpd.GeoDataFrame([cell], crs=self.crs)
            new_cell_gdf = cell_gdf.to_crs('EPSG:4326')
            file_path = os.path.join(output_folder, f'fishnet_cell_{idx}.shp')
            new_cell_gdf.to_file(file_path)