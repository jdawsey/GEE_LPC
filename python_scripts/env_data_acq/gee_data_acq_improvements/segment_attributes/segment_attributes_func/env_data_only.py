import os
import re
import time
import geemap
import segment_attributes_func as saf

"""
Use this function to pull attributes of images to points. Exports as a CSV.
"""
def get_env_data(folder_directory, data_folder, image_stack, shp_dir):
    shp_files = [f for f in os.listdir(shp_dir) if f.endswith('.shp')]
    
    count = len(shp_files)
    print(f'Downloading data for {count} files')

    index_num = -1
    for shp_file in shp_files:
        regex_gcs = re.compile(r'[0-9]_gcs+')
        if not regex_gcs.search(shp_file):
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