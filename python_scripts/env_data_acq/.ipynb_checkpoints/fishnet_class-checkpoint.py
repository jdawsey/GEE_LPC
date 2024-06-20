import os
import geopandas as gpd
from shapely.geometry import box, Point
import numpy as np
import pandas as pd
import fiona

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

    

class Fishnet:
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