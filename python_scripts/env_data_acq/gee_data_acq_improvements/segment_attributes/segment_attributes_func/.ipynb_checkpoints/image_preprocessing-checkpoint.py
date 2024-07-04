import ee
import geemap

def get_imagery(given_ee_object,
                given_collection, 
                start_filter_date = None, 
                end_filter_date = None):
    """
    get_imagery finds images for the dates you want to see
    start_filter_date = string containing the start date for the filter
    end_filter_date = string containing the end date for the filter 
    
    """
    if start_filter_date is None:
        raw_images = ee.ImageCollection(given_collection)\
            .filterBounds(given_ee_object)\
            .mosaic()
        return raw_images
    else:
        raw_images = ee.ImageCollection(given_collection) \
            .filterDate(start_filter_date, end_filter_date)\
            .filterBounds(given_ee_object).mosaic()
        return raw_images





def preprocess_image(image_to_process, given_scale, given_region, band_expressions = None):
    """
    Takes an image its scale and preprocesses it for use with segmentation or classification algorithms.
    image_to_process = the ee image wanting to be processed
    given_scale = the scale of the given image
    """


    # Creates and bands of from user supplied equations
    def add_expressions(given_image, band_expressions = None):
        """
        band_expressions needs to be in a dictionary format where name of band is the key and the expression is the value pair
        """
        expressions_image = given_image
        for key, value in band_expressions.items():
            print(key, value)
            band_math_image = given_image.expression(value).rename(key)
            expressions_image = expressions_image.addBands(band_math_image)
        
        return expressions_image


    def standardize_image(given_image, given_scale, given_geo):
        st_bandNames = given_image.bandNames()
        meanDict = given_image.reduceRegion(
          reducer = ee.Reducer.mean(),
          geometry = given_geo,
          scale = given_scale,
          maxPixels = 1000000,
          bestEffort = True,
          tileScale = 16
        )
        means = ee.Image.constant(meanDict.values(st_bandNames))
        centered = given_image.subtract(means)
    
        stdDevDict = given_image.reduceRegion(
          reducer = ee.Reducer.stdDev(),
          geometry = given_geo,
          scale = given_scale,
          maxPixels = 1000000,
          bestEffort = True,
          tileScale = 16
        )
    
        stddevs = ee.Image.constant(stdDevDict.values(st_bandNames))
        standardized = centered.divide(stddevs)
        return standardized
    # Normalizes all the bands in an image
    """
    def normalize_band(given_image, band_to_process, img_scale, given_image_region):
        band = given_image.select(band_to_process)
        min_value = band.reduceRegion(
            reducer=ee.Reducer.min(),
            #geometry=given_image_region.geometry()
            geometry=given_image_region,
            scale=img_scale,
            maxPixels=1e9
        ).get(band.bandNames().get(0))

        max_value = band.reduceRegion(
            reducer=ee.Reducer.max(),
            #geometry=given_image_region.geometry()
            geometry=given_image_region,
            scale=img_scale,
            maxPixels=1e9
        ).get(band.bandNames().get(0))
        
        normalized = band.subtract(ee.Number(min_value))\
            .divide(ee.Number(max_value).subtract(min_value))
        
        return normalized
    """
    
    # Runs a guassian smoothing filter over the image
    def guassian_smooth(given_image):
        ### gaussian smoothing
        gaussianKernel = ee.Kernel.gaussian(
        radius = 3,
        units = 'pixels'
        )
        
        gaussian_smoothed = given_image.convolve(gaussianKernel)
        return gaussian_smoothed

    # Runs a difference of gaussians sharpening filter over the image
    def dog_sharpening(given_image):
        ### DoG sharpening
        fat = ee.Kernel.gaussian(
        radius = 3,
        sigma = 3,
        magnitude = -1.0,
        units = 'pixels'
        )
        
        skinny = ee.Kernel.gaussian(
        radius = 3,
        sigma = 0.5,
        units = 'pixels'
        )
        
        dog_kernel = fat.add(skinny)
        #changed name from sharpened
        dog_sharp = given_image.add(given_image.convolve(dog_kernel)) # the original dog_method
        #dog_sharp = given_image.convolve(dog_kernel)
        #dog_sharp = dog_sharp.clip(self.ee_object)

        return dog_sharp
    
    image_with_expressions = add_expressions(image_to_process, band_expressions)
    

    # Get the list of band names
    #band_names = image_with_expressions.bandNames().getInfo()
    # Normalize each band
    #normalized_bands = [normalize_band(image_with_expressions, band, given_scale, given_region) for band in band_names]
    # Combine normalized bands into a single image
    #normalized_image = ee.Image.cat(normalized_bands).rename(band_names)
    standardized = standardize_image(image_with_expressions, given_scale, given_region)

    gaussian_image = guassian_smooth(standardized)
    dog_sharpened = dog_sharpening(gaussian_image)


    return dog_sharpened

