import os
import re
import time
import geemap
import segment_attributes_func as saf

"""
Download imagery per the area of all the shapefiles in a folder.
folder_directory = The broader directory. Used to determine where the shapefile folder and data folder will be.
data_folder = the folder that the imagery will download to.
image_stack = the image with all the desired bands to be downloaded.
shp_dir = the directory address to the folder containing each of the shapefiles.
"""
def imagery_download(folder_directory, data_folder, image_stack, shp_dir, scale = 30, 
                     get_segment_attributes=True):
    shp_files = [f for f in os.listdir(shp_dir) if f.endswith('.shp')]

    count = 0
    # Iterate directory
    for path in os.listdir(shp_dir):
        # check if current path is a file
        if path.endswith('.shp'):
            count += 1
    print(f'Downloading data for {count} files')
    
    index_num = -1
    for shp_file in shp_files:
        regex_gcs = re.compile(r'[0-9]_gcs+')
        if (regex_gcs.search(shp_file) == None) == True:
            if get_segment_attributes is True:
                index_num = index_num + 1
                shp_path = os.path.join(shp_dir, shp_file)
                feature_collection = geemap.shp_to_ee(shp_path)
                feature = feature_collection.geometry()
                
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

                segment_bands = ['R_1', 'G_1', 'B_1', 'N_1', 'savi_1', 
                                 'endvi_1', 'area', 'perimeter', 'width', 'height']
                segment_bands_rename = ['red_mean', 'green_mean', 'blue_mean', 
                                        'nir_mean', 'savi_mean', 'endvi_mean', 
                                        'area', 'perimeter', 'width', 'height']
                try:
                    segment_attributes = segmented.select(segment_bands).rename(segment_bands_rename)
                except Exception as e:
                    print(f"Error selecting and renaming segment attributes: {e}")
                    continue
                
                try:
                    image_stack_w_segments = image_stack.addBands(segment_attributes)
                except Exception as e:
                    print(f"Error adding bands to image stack: {e}")
                    continue
                    """
                out_csv = f'{folder_directory}/{data_folder}/cell_{index_num}_with_env_data.csv'
                try:
                    response = geemap.extract_values_to_points(feature_collection, image_stack, out_csv)
                    print(f"Response: {response}")
                except Exception as e:
                    print(f"Error extracting values to points: {e}")
                    continue
                    """
            
                image_path = f'{folder_directory}/{data_folder}/cell_{index_num}_env_image.tif'
                geemap.ee_export_image(image_stack_w_segments, image_path, scale, region = feature)
                print(f'Export task started for {shp_file}.')
                time.sleep(15)
            else:
                index_num = index_num + 1
                shp_path = os.path.join(shp_dir, shp_file)
                feature_collection = geemap.shp_to_ee(shp_path)
                feature = feature_collection.geometry()
                image_path = f'{folder_directory}/{data_folder}/cell_{index_num}_env_image.tif'
                geemap.ee_export_image(image_stack, image_path, scale, region = feature)
                print(f'Export task started for {shp_file}.')
                time.sleep(15)
                
        else:
            print("skipping gcs file")

    
    regex_gcs = re.compile(r'[0-9]_gcs+')
    delete_file_path = f'{shp_dir}/'
    delete_file_paths = os.listdir(delete_file_path)
    for file in delete_file_paths:
        full_path = f'{delete_file_path}{file}'
        if (regex_gcs.search(full_path) == None) == False:
            os.remove(full_path)
            print(f'removed {full_path}')