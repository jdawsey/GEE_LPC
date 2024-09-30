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