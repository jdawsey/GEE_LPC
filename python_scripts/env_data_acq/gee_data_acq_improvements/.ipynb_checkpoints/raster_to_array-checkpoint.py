import numpy as np
from osgeo import gdal, ogr, osr
import sklearn
import xgboost as xgb
import os


### Allows for the conversion of a raster to a numpy array so that an XGBoost classification 
### model can be applied to it on a per cell basis. Then it allows for the export of the new 
### raster.
class RasterToArrayConverter:
    def __init__(self, raster_path, shapefile_path=None, mask_value=0, continue_on_empty_bands=False):
        self.raster_path = raster_path
        self.shapefile_path = shapefile_path
        self.dataset = None
        self.num_bands = 0
        self.band_arrays = None
        self.combined_array = None
        self.geotransform = None
        self.projection = None
        self.mask_value = mask_value
        self.mask = None
        self.nan_band_indices = []  # List to store indices of bands that are all NaNs
        self.continue_on_empty_bands = continue_on_empty_bands

    def open_raster(self):
        self.dataset = gdal.Open(self.raster_path, gdal.GA_ReadOnly)
        if not self.dataset:
            raise FileNotFoundError(f"Unable to open {self.raster_path}")
        self.num_bands = self.dataset.RasterCount
        if self.num_bands == 0:
            raise ValueError(f"No bands found in {self.raster_path}")
        self.geotransform = self.dataset.GetGeoTransform()
        self.projection = self.dataset.GetProjection()

    def apply_external_mask(self, keep_covered_pixels=True):
        if not self.shapefile_path:
            print("No external mask provided. Proceeding without external masking.")
            return
        
        if not os.path.exists(self.shapefile_path):
            raise FileNotFoundError(f"Shapefile {self.shapefile_path} not found.")
        
        # Open the shapefile
        shapefile = ogr.Open(self.shapefile_path)
        if not shapefile:
            raise ValueError(f"Unable to open shapefile {self.shapefile_path}")
        
        # Get the layer from the shapefile
        layer = shapefile.GetLayer()
        if layer.GetGeomType() != ogr.wkbPolygon:
            raise ValueError("Shapefile must contain polygons.")

        # Create a temporary raster to rasterize the shapefile
        temp_raster_path = 'temp_mask.tif'
        x_res = self.dataset.RasterXSize
        y_res = self.dataset.RasterYSize
        temp_raster = gdal.GetDriverByName('GTiff').Create(temp_raster_path, x_res, y_res, 1, gdal.GDT_Byte)
        temp_raster.SetGeoTransform(self.geotransform)
        temp_raster.SetProjection(self.projection)
        temp_raster.GetRasterBand(1).Fill(0)
        temp_raster.GetRasterBand(1).SetNoDataValue(0)

        # Rasterize the shapefile layer into the temporary raster
        gdal.RasterizeLayer(temp_raster, [1], layer, burn_values=[255])

        # Read the mask array from the temporary raster
        mask_band = temp_raster.GetRasterBand(1)
        mask_array = mask_band.ReadAsArray()

        # Clean up: close raster dataset and delete temporary file
        temp_raster = None
        os.remove(temp_raster_path)

        # Create the mask based on the user preference
        if keep_covered_pixels:
            self.mask = np.where(mask_array == 255, np.nan, 1)
        else:
            self.mask = np.where(mask_array == 255, 1, np.nan)

        print(f"External mask applied from shapefile. Mask shape: {self.mask.shape}, Number of masked pixels: {np.sum(np.isnan(self.mask))}")

    def read_bands(self, verbose = True):
        self.band_arrays = []
        self.mask = None

        if self.shapefile_path:
            self.apply_external_mask()

        for b in range(1, self.num_bands + 1):
            band = self.dataset.GetRasterBand(b)
            band_array = band.ReadAsArray()
            # Replace mask_value values with NaN for masking
            band_array = np.where(band_array == self.mask_value, np.nan, band_array)

            if verbose == False:
                pass
            else:
                # Debugging information
                print(f"Band {b} - Shape: {band_array.shape}, NaNs: {np.isnan(band_array).sum()}")

            if np.isnan(band_array).all():
                # If the entire band is NaN, store the index and skip this band
                self.nan_band_indices.append(b - 1)
                band_array[:] = np.nan  # Use NaNs as a placeholder
                self.band_arrays.append(band_array)
                continue
            
            if self.mask is None:
                self.mask = np.isnan(band_array)
            else:
                self.mask |= np.isnan(band_array)
            self.band_arrays.append(band_array)
        
        # Debugging information
        print(f"Mask shape: {self.mask.shape}, Number of masked pixels: {np.sum(self.mask)}")

        # Notify user about empty bands and ask for confirmation to continue if not already specified
        if self.nan_band_indices and not self.continue_on_empty_bands:
            num_empty_bands = len(self.nan_band_indices)
            user_input = input(f"{num_empty_bands} bands are empty. Do you want to continue? (yes/no): ")
            if user_input.lower() != 'yes':
                print("Process aborted by user.")
                return False
        return True

    def combine_bands(self):
        if not self.band_arrays:
            raise ValueError("Band arrays not read. Call read_bands() first.")
        self.combined_array = np.stack(self.band_arrays, axis=-1)

    def apply_model(self, model, binary=False):
        if self.combined_array is None:
            raise ValueError("Combined array not created. Call combine_bands() first.")
        
        # Reshape array to (num_pixels, num_bands)
        height, width, num_bands = self.combined_array.shape
        reshaped_array = self.combined_array.reshape(-1, num_bands)

        # Apply mask to exclude masked pixels
        if self.mask is not None:
            valid_pixels = ~self.mask.reshape(-1)
            reshaped_array_valid = reshaped_array[valid_pixels]
        else:
            reshaped_array_valid = reshaped_array

        # Debugging information
        print(f"reshaped_array shape: {reshaped_array.shape}")
        if self.mask is not None:
            print(f"valid_pixels shape: {valid_pixels.shape}")
            print(f"Number of valid pixels: {np.sum(valid_pixels)}")
        
        if reshaped_array_valid.shape[0] == 0:
            raise ValueError("No valid pixels found after applying mask.")

        if binary:
            predictions = model.predict(reshaped_array_valid)

            # Create an array to hold the result and apply the mask if available
            if self.mask is not None:
                result_array = np.full((height * width), self.mask_value, dtype=int)
                result_array[valid_pixels] = predictions
            else:
                result_array = predictions
            
            # Reshape result back to (height, width)
            result_array = result_array.reshape(height, width)
            return result_array

        else:
            # Make predictions
            proba_predictions = model.predict_proba(reshaped_array_valid)
            
            # Print shape and contents of proba_predictions for debugging
            print(f"proba_predictions shape: {proba_predictions.shape}")
            print(f"proba_predictions: {proba_predictions}")

            # Check if proba_predictions has the expected shape
            if proba_predictions.shape[1] < 2:
                raise ValueError("Model does not return probabilities for two classes. Check the model and its training data.")
            
            # Assuming binary classification and exporting probabilities for the positive class
            positive_class_probs = proba_predictions[:, 1]

            # Convert probabilities to integers (e.g., 0.95 -> 95)
            positive_class_probs_int = (positive_class_probs * 100).astype(int)

            # Create an array to hold the result and apply the mask if available
            if self.mask is not None:
                result_array = np.full((height * width), self.mask_value, dtype=int)
                result_array[valid_pixels] = positive_class_probs_int
            else:
                result_array = positive_class_probs_int
            
            # Reshape result back to (height, width)
            result_array = result_array.reshape(height, width)
            return result_array

    def append_nan_bands(self, result_array):
        height, width = result_array.shape
        for index in self.nan_band_indices:
            # Create a NaN band with the same shape as the result_array
            nan_band = np.full((height, width), np.nan)
            # Insert the NaN band at the correct index
            self.band_arrays.insert(index, nan_band)
        self.combined_array = np.stack(self.band_arrays, axis=-1)
        return self.combined_array

    def create_georeferenced_raster(self, output_path, array):
        if self.geotransform is None or self.projection is None:
            raise ValueError("Georeferencing information not available. Call open_raster() first.")
        
        # Get the dimensions
        rows, cols = array.shape
        
        # Create the output dataset
        driver = gdal.GetDriverByName('GTiff')
        out_dataset = driver.Create(output_path, cols, rows, 1, gdal.GDT_Float32)
        out_dataset.SetGeoTransform(self.geotransform)
        out_dataset.SetProjection(self.projection)
        
        # Write the array to the first band
        out_band = out_dataset.GetRasterBand(1)
        out_band.WriteArray(array)
        
        # Close the output dataset
        out_dataset.FlushCache()
        out_dataset = None