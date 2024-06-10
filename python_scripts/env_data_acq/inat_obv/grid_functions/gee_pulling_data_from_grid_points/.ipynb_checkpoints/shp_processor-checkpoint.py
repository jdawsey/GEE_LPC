import os
import geopandas as gpd
import pandas as pd
import ee
import geemap
import time


class shpProcessor:
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
            index_num = index_num + 1
            shp_path = os.path.join(self.shp_dir, shp_file)
            feature_collection = geemap.shp_to_ee(shp_path)
            out_csv = f'{self.folder_directory}/{self.data_folder}/cell_{index_num}_with_env_data.csv'
            geemap.extract_values_to_points(feature_collection, self.image_stack, out_csv)
            print(f'Export task started for {shp_file}.')
            time.sleep(15)
