import os
import geopandas as gpd
import pandas as pd
import ee
import geemap


###############
# Modify so can resample and reproject bands if needed

class ImageStackBuilder:
    def __init__(self, image_collections):
        self.image_collections = image_collections

    def build_image_stack(self, user_specified = None):
        images = []
        
        if user_specified is None:
            for index in range(len(self.image_collections)):
                collection_loc = self.image_collections.loc[index, 'collection_loc']
                band_rename = self.image_collections.loc[index, 'band_rename']
                bands_rename_list = band_rename.split()
                image_bands = self.image_collections.loc[index, 'bands']
                image_band_list = image_bands.split()
                if self.image_collections.loc[index, 'resample'] == True:
                    asset_image = ee.Image(collection_loc)
                    #print("this is true")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.resample('bicubic').reproject('EPSG:4326', scale = self.image_collections.loc[index, 'resample_res'])
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
                else:
                    asset_image = ee.Image(collection_loc)
                    #print("this is false")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
            return ee.Image(images)
            
        else:
            for index in range(len(self.image_collections)):
                collection_loc = self.image_collections.loc[index, 'collection_loc']
                band_rename = self.image_collections.loc[index, 'band_rename']
                bands_rename_list = band_rename.split()
                image_bands = self.image_collections.loc[index, 'bands']
                image_band_list = image_bands.split()
                if self.image_collections.loc[index, 'resample'] == True:
                    asset_image = ee.Image(collection_loc)
                    #print("this is true")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.resample('bicubic').reproject('EPSG:4326', scale = self.image_collections.loc[index, 'resample_res'])
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
                else:
                    asset_image = ee.Image(collection_loc)
                    #print("this is false")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)

            user_created_bands = ee.Image([user_specified])
            original_bands = ee.Image([images])
            merged_bands = original_bands.addBands(user_created_bands)
            return merged_bands