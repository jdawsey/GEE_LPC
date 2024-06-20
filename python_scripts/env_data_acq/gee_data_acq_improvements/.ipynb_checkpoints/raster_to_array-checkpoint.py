import numpy as np
from osgeo import gdal
import sklearn
import xgboost as xgb


### Allows for the conversion of a raster to a numpy array so that an XGBoost classification 
### model can be applied to it on a per cell basis. Then it allows for the export of the new 
### raster.
class RasterToArrayConverter:
    def __init__(self, raster_path, mask_value=0):
        self.raster_path = raster_path
        self.dataset = None
        self.num_bands = 0
        self.band_arrays = None
        self.combined_array = None
        self.geotransform = None
        self.projection = None
        self.mask_value = mask_value
        self.mask = None
        
    def open_raster(self):
        self.dataset = gdal.Open(self.raster_path, gdal.GA_ReadOnly)
        if not self.dataset:
            raise FileNotFoundError(f"Unable to open {self.raster_path}")
        self.num_bands = self.dataset.RasterCount
        if self.num_bands == 0:
            raise ValueError(f"No bands found in {self.raster_path}")
        self.geotransform = self.dataset.GetGeoTransform()
        self.projection = self.dataset.GetProjection()
    
    def read_bands(self):
        self.band_arrays = []
        self.mask = None
        for b in range(1, self.num_bands + 1):
            band = self.dataset.GetRasterBand(b)
            band_array = band.ReadAsArray()
            # Replace 0 values with NaN for masking
            band_array = np.where(band_array == self.mask_value, np.nan, band_array)
            if self.mask is None:
                self.mask = np.isnan(band_array)
            else:
                self.mask |= np.isnan(band_array)
            self.band_arrays.append(band_array)
    
    def combine_bands(self):
        if not self.band_arrays:
            raise ValueError("Band arrays not read. Call read_bands() first.")
        self.combined_array = np.stack(self.band_arrays, axis=-1)
    
    
    def apply_model(self, model, binary = "False"):
        if self.combined_array is None:
            raise ValueError("Combined array not created. Call combine_bands() first.")
        
        # Reshape array to (num_pixels, num_bands)
        height, width, num_bands = self.combined_array.shape
        reshaped_array = self.combined_array.reshape(-1, num_bands)

        # Apply mask to exclude masked pixels
        valid_pixels = ~self.mask.reshape(-1)
        reshaped_array_valid = reshaped_array[valid_pixels]

        # if just want the binary classification
        if binary == True:
            predictions = model.predict(reshaped_array_valid)

            # Create an array to hold the result and apply the mask
            result_array = np.full((height * width), self.mask_value, dtype=int)
            result_array[valid_pixels] = predictions
            
            # Reshape result back to (height, width)
            result_array = result_array.reshape(height, width)
            return result_array

        # if want the probabilities
        else:
            # Make predictions
            proba_predictions = model.predict_proba(reshaped_array_valid)
            #predictions = model.predict(reshaped_array)
        
            # Assuming binary classification and exporting probabilities for the positive class
            positive_class_probs = proba_predictions[:, 1]

            # Convert probabilities to integers (e.g., 0.95 -> 95)
            positive_class_probs_int = (positive_class_probs * 100).astype(int)

            # Create an array to hold the result and apply the mask
            result_array = np.full((height * width), self.mask_value, dtype=int)
            result_array[valid_pixels] = positive_class_probs_int
            
            # Reshape result back to (height, width)
            result_array = result_array.reshape(height, width)
            return result_array
    
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
    
    def convert(self):
        self.open_raster()
        self.read_bands()
        self.combine_bands()
        return self.combined_array
    
    def close_raster(self):
        self.dataset = None

