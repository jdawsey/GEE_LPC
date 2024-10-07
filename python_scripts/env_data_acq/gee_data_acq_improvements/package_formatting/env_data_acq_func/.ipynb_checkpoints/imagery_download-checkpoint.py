import os
import re
import time
import geemap

"""
Download imagery per the area of all the shapefiles in a folder.
folder_directory = The broader directory. Used to determine where the shapefile folder and data folder will be.
data_folder = the folder that the imagery will download to.
image_stack = the image with all the desired bands to be downloaded.
shp_dir = the directory address to the folder containing each of the shapefiles.
"""
def imagery_download(folder_directory, data_folder, image_stack, shp_dir, 
                     scale = 30):
    # cleaning out any extra files in case ran previously
    delete_file_path = f'{shp_dir}/'
    delete_file_paths = os.listdir(delete_file_path)
    for file in delete_file_paths:
        if (re.search(r'[0-9]_gcs+', file)) or (re.search(r'[a-zA-Z]_gcs+', file)):
            full_path = f'{delete_file_path}{file}'
            print(full_path)
            os.remove(full_path)
            print(f'removed {file}')
    
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
        index_num = index_num + 1
        file_name_split = shp_file.split(".")
        
        shp_path = os.path.join(shp_dir, shp_file)
        feature_collection = geemap.shp_to_ee(shp_path)
        feature = feature_collection.geometry()
        image_path = f'{folder_directory}/{data_folder}/{file_name_split[0]}_env_image.tif'
        geemap.ee_export_image(image_stack, image_path, scale, region = feature)
        print(f'Export task started for {shp_file}.')
        time.sleep(15)