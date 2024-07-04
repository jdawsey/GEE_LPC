import os
import geopandas as gpd
from shapely.geometry import box, Point
import numpy as np
import pandas as pd
import fiona
import ee
import geemap
import time
import re
import rasterio
from rasterio.windows import from_bounds



### Allows for the generation of an ee.Image containing n-bands specified by the user.
### It pulls the bands from a CSV file, renames them, and will resample them to the 
### desired resolution.
class ImageStackBuilder:
    def __init__(self, image_collections):
        self.image_collections = image_collections

    def build_image_stack(self, user_specified = None, rast_crs = 'EPSG:4326'):
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
                    resample_scale = int(self.image_collections.loc[index, 'resample_res'])
                    rasample_method = str(self.image_collections.loc[index, 'resample_method'])
                    #print("this is true")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.resample(resample_method).reproject(rast_crs, scale = resample_scale)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
                else:
                    asset_image = ee.Image(collection_loc)
                    #print("this is false")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]]).reproject(rast_crs)
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
                    resample_scale = int(self.image_collections.loc[index, 'resample_res'])
                    resample_method = str(self.image_collections.loc[index, 'resample_method'])
                    #print("this is true")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]])
                        band_select = band_select.resample(resample_method).reproject(rast_crs, scale = resample_scale)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)
                else:
                    asset_image = ee.Image(collection_loc)
                    #print("this is false")
                    for image_band_index in range(len(image_band_list)):
                        band_select = asset_image.select([image_band_list[image_band_index]]).reproject(rast_crs)
                        band_select = band_select.rename(bands_rename_list[image_band_index])
                        images.append(band_select)

            user_created_bands = ee.Image([user_specified])
            original_bands = ee.Image([images])
            merged_bands = original_bands.addBands(user_created_bands)
            return merged_bands
