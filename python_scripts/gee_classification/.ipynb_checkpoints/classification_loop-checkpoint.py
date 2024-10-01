import os
import re
import time
import ee
import geemap
import segment_testing_my_gee_functions as mgf
import sys
import io

"""
Download imagery per the area of all the shapefiles in a folder.
folder_directory = The broader directory. Used to determine where the shapefile folder and data folder will be.
data_folder = the folder that the imagery will download to.
shp_dir = the directory address to the folder containing each of the shapefiles.
"""
def download_classified(folder_directory, data_folder, shp_dir, scale = 1):
    # gaining a list of all the files in the given folder
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
            # increase the index by one for file searching and for creation later
            index_num = index_num + 1
            # create the path to the start shapefile (polygon area)
            shp_path = os.path.join(shp_dir, shp_file)
            # create a feature collection from the feature
            feature_collection = geemap.shp_to_ee(shp_path)
            # find the features geometry so can be used for calculations 
            feature_geom = feature_collection.geometry()

            naip = mgf.naip_func(feature_collection)
            
            savi = mgf.naip_savi_endvi(naip)
            
            def gauss_three_func(given_image):
                ### gaussian smoothing
                gaussianKernel = ee.Kernel.gaussian(
                  radius = 3, # was originally 3, also tested 10
                  units = 'pixels'
                )
                
                gaussian_smooth = given_image.convolve(gaussianKernel)
                return gaussian_smooth
            
            gauss = gauss_three_func(savi)
            vis_param_smooth = {'bands' : ['R', 'G', 'B'], 
                           'min' : 0, 
                           'max' : 256,
                           'gamma' : 1}

            # creating a grayscale image for the glcm
            grayscale = naip.expression(
                  '(0.3 * R) + (0.59 * G) + (0.11 * B)', {
                  'R': naip.select(['R']),
                  'G': naip.select(['G']),
                  'B': naip.select(['B'])
            })
            
            # if wanting to use a grayscale image
            int_gray = grayscale.int()
            glcmTexture = int_gray.glcmTexture(5)

            # selecting just those necessary bands
            imp_glcm_bands = glcmTexture.select(['constant_savg', 'constant_contrast'])

            # adding the rng bands back
            glcm_segment = imp_glcm_bands.addBands(gauss, ['R', 'G', 'B', 'N', 'savi']) #may need to include 'savi' and 'endvi'

            # standardizing the imagery
            standardized = mgf.stdrd_func(glcm_segment, feature_collection)
            
            # point-based algorithm
            max_clusters = 10 # tested with 10
            
            classified = mgf.pb_class(feature_collection, standardized, max_clusters)


            # creating a path for the classified image to export to
            filename = f'{folder_directory}/{data_folder}/cell_{index_num}_env_image.tif'
            # export the final classified image
            geemap.ee_export_image(classified, filename, scale, region = feature_geom)
            print(f'Export task started for {shp_file}.')

                        # Function to log the result to a text file
            def log_result(status, filename, error_message=None):
                with open(f"{folder_directory}/task_log.txt", "a") as log_file:
                    if status == "Data downloaded":
                        log_file.write(f"{filename}: {status}\n")
                    elif status == "An error occurred":
                        log_file.write(f"{filename}: {status} (Unknown error)\n")
                    else:
                        log_file.write(f"{filename}: {status} (Error: {error_message})\n")
            
            # Redirect console output
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
    
            # Restore console output
            sys.stdout = old_stdout
    
            # Capture the console output as a string
            output = buffer.getvalue()
            
            # Check if the image was saved
            if "Data downloaded" in output:
                log_result("Success", filename)
            else:
                log_result("An error occurred", filename)
            
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