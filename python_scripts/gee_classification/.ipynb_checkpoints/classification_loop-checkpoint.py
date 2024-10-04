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
max_clusters = the number of clusters for the k-means algorithm to use
fishnet_rows = the number of rows for the fishnet to generate when exporting imagery
fishnet_cols = the number of columns for the fishnet to generate when exporting imagery
scale = the scale of the imagery to export
error_log = Generation of an error log of exported files if requested.
"""
def download_classified_thumbnails(folder_directory, data_folder, shp_dir, 
                                   max_clusters = 10, fishnet_rows = 5, 
                                   fishnet_cols = 5, scale = 1, error_log = False):
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
            
            # point-based classification algorithm
            classified_image = mgf.pb_class(feature_collection, standardized, max_clusters)

            # Generate a fishnet grid over the AOI (set cell size in degrees or meters)
            fishnet = geemap.fishnet(feature_geom, fishnet_rows=5, fishnet_cols=5)

            # Convert the fishnet (FeatureCollection) to a list of features
            fishnet_list = fishnet.toList(fishnet.size())

            grid_cell_num = 0
            # Loop through each cell of the fishnet and clip the image
            for i in range(fishnet.size().getInfo()):
                grid_cell_num = grid_cell_num + 1

                # Get the individual grid cell (Feature)
                grid_cell = ee.Feature(fishnet_list.get(i)).geometry()

                # Clip the classified image by the current grid cell
                clipped_image = classified_image.clip(grid_cell)

                # creating a path for the classified image to export to
                cellname = f'cell_{index_num}_gridcell_{grid_cell_num}_classified'
                filename = f'{folder_directory}/{data_folder}/{cellname}.tif'
            
                geemap.ee_export_image(clipped_image, filename, scale, region = grid_cell)
                print(f'Export task started for {cellname}.')

                # an if-else statement to generate a textfile error log if wanted. Defaults to false.
                if error_log == True:
    
                    # Function to log the result to a text file
                    def log_result(status, filename, error_message=None):
                        with open(f"{folder_directory}/task_log.txt", "a") as log_file:
                            if status == "Data downloaded":
                                log_file.write(f"{cellname}: {status}\n")
                            elif status == "An error occurred":
                                log_file.write(f"{cellname}: {status} (Unknown error)\n")
                            else:
                                log_file.write(f"{cellname}: {status} (Error: {error_message})\n")
                
                    # Redirect console output
                    old_stdout = sys.stdout
                    sys.stdout = buffer = io.StringIO()
            
                    # Restore console output
                    sys.stdout = old_stdout
            
                    # Capture the console output as a string
                    output = buffer.getvalue()
                    
                    # Check if the image was saved
                    if "Data downloaded" in output:
                        log_result("Success", cellname)
                    else:
                        log_result("An error occurred", cellname)
                else:
                    pass
            
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


"""
Download imagery per the area of all the shapefiles in a folder.
folder_directory = The broader directory. Used to determine where the shapefile folder and data folder will be.
data_folder = the google drive folder that the imagery will download to.
shp_dir = the directory address to the folder containing each of the shapefiles.
n_clusters = the number of clusters for the k-means algorithm to use
scale = the scale of the imagery to export
max_pixels = the maximum number of pixels for the program to export
"""
def download_classified_drive(folder_directory, data_folder, shp_dir, max_pixels, 
                                n_clusters = 10, scale = 1, ):
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
            
            # point-based classification algorithm
            classified_image = mgf.pb_class(feature_collection, standardized, n_clusters)

            # creating a path for the classified image to export to
            cellname = f'cell_{index_num}_classified'
        
            print(f'Export task started for {cellname}.')

            task_pb = ee.batch.Export.image.toDrive(
                image = classified_image,
                description = cellname,
                folder = data_folder, #!imagery
                region = feature_geom,
                scale = scale,
                crs = 'EPSG:6350',
                maxPixels = max_pixels
            )
            task_pb.start()
            
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