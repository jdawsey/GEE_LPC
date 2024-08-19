import os
import re
import time
import geemap
import segment_attributes_func as saf

"""
Use this function to pull attributes of images to points. Exports as a CSV.
"""
def get_segment_attributes(folder_directory, data_folder, shp_dir):
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

            segment_bands = ['R_1', 'G_1', 'B_1', 'N_1', 'savi_1', 'endvi_1', 
                             'area', 'perimeter', 'width', 'height']
            segment_bands_rename = ['red_mean', 'green_mean', 'blue_mean', 
                                    'nir_mean', 'savi_mean', 'endvi_mean', 
                                    'area', 'perimeter', 'width', 'height']
            try:
                segment_attributes = segmented.select(segment_bands).rename(segment_bands_rename)
            except Exception as e:
                print(f"Error selecting and renaming segment attributes: {e}")
                continue

            out_csv = f'{folder_directory}/{data_folder}/cell_{index_num}_segment_data.csv'
            response = geemap.extract_values_to_points(feature_collection, segment_attributes, out_csv)
            #print(f"Response: {response}")

            print(f'Export task started for {shp_file}.')
            response
            time.sleep(15)
        else:
            print("skipping gcs file")

    delete_file_paths = [f for f in os.listdir(shp_dir) if regex_gcs.search(f)]
    for file in delete_file_paths:
        full_path = os.path.join(shp_dir, file)
        os.remove(full_path)
        print(f'removed {full_path}')