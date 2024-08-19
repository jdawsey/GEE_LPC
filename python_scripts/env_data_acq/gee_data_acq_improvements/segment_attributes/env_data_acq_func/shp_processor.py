import os
import re
import time
import geemap
import segment_attributes_func as saf

"""
Use this function to pull attributes of images to points. Exports as a CSV.
"""
def process_shp_files(folder_directory, data_folder, image_stack, shp_dir, get_segment_attributes=True, segment_attributes=None):
    shp_files = [f for f in os.listdir(shp_dir) if f.endswith('.shp')]
    
    count = len(shp_files)
    print(f'Downloading data for {count} files')

    index_num = -1
    for shp_file in shp_files:
        regex_gcs = re.compile(r'[0-9]_gcs+')
        if not regex_gcs.search(shp_file):
            if get_segment_attributes is True:
                index_num += 1
                shp_path = os.path.join(shp_dir, shp_file)
                
                try:
                    feature_collection = geemap.shp_to_ee(shp_path)
                except Exception as e:
                    print(f"Error converting shapefile to ee.FeatureCollection: {e}")
                    continue

                try:
                    polygon_imagery = saf.get_imagery(feature_collection, 'USDA/NAIP/DOQQ', 
                                                      start_filter_date='2016-01-01', end_filter_date='2016-12-31')
                except Exception as e:
                    print(f"Error getting imagery: {e}")
                    continue

                band_maths = {'savi': '((1 + 0.6) * (b("N") - b("R"))) / (b("N") + b("R") + 0.5)',
                              'endvi': '((b("N") + b("G")) - (2 * b("B"))) / ((b("N") + b("G")) + (2 + b("B")))'}
                try:
                    preprocessed = saf.preprocess_image(polygon_imagery, given_scale=1, 
                                                        given_region=feature_collection, band_expressions=band_maths)
                except Exception as e:
                    print(f"Error preprocessing image: {e}")
                    continue

                try:
                    segmented = saf.segmentation_attributes(preprocessed)
                except Exception as e:
                    print(f"Error getting segmentation attributes: {e}")
                    continue

                segment_bands = ['R_1', 'G_1', 'B_1', 'N_1', 'savi_1', 'endvi_1', 'area', 'perimeter', 'width', 'height']
                segment_bands_rename = ['red_mean', 'green_mean', 'blue_mean', 'nir_mean', 'savi_mean', 'endvi_mean', 'area', 'perimeter', 'width', 'height']
                try:
                    segment_attributes = segmented.select(segment_bands).rename(segment_bands_rename)
                except Exception as e:
                    print(f"Error selecting and renaming segment attributes: {e}")
                    continue
                
                try:
                    #image_stack_w_seg = image_stack.addBands(segment_attributes)
                    image_stack_w_seg = image_stack.addBands(segmented)
                except Exception as e:
                    print(f"Error adding bands to image stack: {e}")
                    continue

                out_csv = f'{folder_directory}/{data_folder}/cell_{index_num}_with_env_data.csv'
                try:
                    response = geemap.extract_values_to_points(feature_collection, image_stack_w_seg, out_csv)
                    #print(f"Response: {response}")
                except Exception as e:
                    print(f"Error extracting values to points: {e}")
                    continue

                print(f'Export task started for {shp_file}.')
                response
                time.sleep(15)
            else:
                index_num += 1
                shp_path = os.path.join(shp_dir, shp_file)
                
                try:
                    feature_collection = geemap.shp_to_ee(shp_path)
                except Exception as e:
                    print(f"Error converting shapefile to ee.FeatureCollection: {e}")
                    continue

                out_csv = f'{folder_directory}/{data_folder}/cell_{index_num}_with_env_data.csv'
                try:
                    response = geemap.extract_values_to_points(feature_collection, image_stack, out_csv)
                    print(f"Response: {response}")
                except Exception as e:
                    print(f"Error extracting values to points: {e}")
                    continue

                print(f'Export task started for {shp_file}.')
                time.sleep(15)
        else:
            print("skipping gcs file")

    delete_file_paths = [f for f in os.listdir(shp_dir) if regex_gcs.search(f)]
    for file in delete_file_paths:
        full_path = os.path.join(shp_dir, file)
        os.remove(full_path)
        print(f'removed {full_path}')


"""
def process_shp_files(folder_directory, data_folder, image_stack, shp_dir, get_segment_attributes = True, segment_attributes = None):
    shp_files = [f for f in os.listdir(shp_dir) if f.endswith('.shp')]
    
    count = len(shp_files)
    print(f'Downloading data for {count} files')

    index_num = -1
    for shp_file in shp_files:
        regex_gcs = re.compile(r'[0-9]_gcs+')
        if not regex_gcs.search(shp_file):
            if get_segment_attributes is True:
                index_num += 1
                shp_path = os.path.join(shp_dir, shp_file)
                feature_collection = geemap.shp_to_ee(shp_path)

                # Need to clean this up so it merges seamlessly and works for a user who want to do custom stuff
                polygon_imagery = saf.get_imagery(feature_collection, 'USDA/NAIP/DOQQ', start_filter_date='2016-01-01', end_filter_date='2016-12-31')
                band_maths = {'savi' : '((1 + 0.6) * (b("N") - b("R"))) / (b("N") + b("R") + 0.5)',
                              'endvi' : '((b("N") + b("G")) - (2 * b("B"))) / ((b("N") + b("G")) + (2 + b("B")))'}
                preprocessed = saf.preprocess_image(polygon_imagery, given_scale = 1, given_region = feature_collection, band_expressions=band_maths)
                segmented = saf.segmentation_attributes(preprocessed)
                segment_bands = ['R_1', 'G_1', 'B_1', 'N_1', 'savi_1', 'endvi_1', 'area', 'perimeter', 'width', 'height']
                segment_bands_rename = ['red_mean', 'green_mean', 'blue_mean', 'nir_mean', 'savi_mean', 'endvi_mean', 'area', 'perimeter', 'width', 'height']
                segment_attributes = segmented.select(segment_bands).rename(segment_bands_rename)
                image_stack.addBands(segment_attributes)
                
                out_csv = f'{folder_directory}/{data_folder}/cell_{index_num}_with_env_data.csv'
                geemap.extract_values_to_points(feature_collection, image_stack, out_csv)
                print(f'Export task started for {shp_file}.')
                time.sleep(15)
            else:
                index_num += 1
                shp_path = os.path.join(shp_dir, shp_file)
                feature_collection = geemap.shp_to_ee(shp_path)
                out_csv = f'{folder_directory}/{data_folder}/cell_{index_num}_with_env_data.csv'
                geemap.extract_values_to_points(feature_collection, image_stack, out_csv)
                print(f'Export task started for {shp_file}.')
                time.sleep(15)
        else:
            print("skipping gcs file")

    delete_file_paths = [f for f in os.listdir(shp_dir) if regex_gcs.search(f)]
    for file in delete_file_paths:
        full_path = os.path.join(shp_dir, file)
        os.remove(full_path)
        print(f'removed {full_path}')
"""

"""

import os
import geopandas as gpd
import pandas as pd
import ee
import geemap
import time
import re


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
"""
