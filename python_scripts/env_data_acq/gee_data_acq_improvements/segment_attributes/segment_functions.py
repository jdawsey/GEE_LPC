import ee
import geemap


class PreprocessImagery:
    def __init__(self, given_shapefile, image_collection):
        """
        Supplies the imagery wanting to be processed for your region.
        
        given_shapefile = this is the shapefile you supply
        image_collection is a string containing the collection you want to use"""
        self.given_shapefile = given_shapefile
        self.ee_object = geemap.shp_to_ee(self.given_shapefile)
        self.image_collection = image_collection
        self.imagery = self.get_imagery()
    
    def get_imagery(self, start_filter_date = None, end_filter_date = None):
        """
        get_imagery finds images for the dates you want to see
        start_filter_date = string containing the start date for the filter
        end_filter_date = string containing the end date for the filter 
        
        """
        if start_filter_date == None:
            raw_images = ee.ImageCollection(self.image_collection).filterBounds(self.ee_object).mosaic()
            return raw_images
        else:
            raw_images = ee.ImageCollection(self.image_collection).filterDate(start_filter_date, end_filter_date).filterBounds(self.ee_object).mosaic()
            return raw_images
    
    def image_preprocess(self, band_expressions = None):
        """
        band_expressions needs to be in a dictionary format where name of band is the key and the expression is the value pair
        """
        expressions_image = self.imagery
        if band_expressions == None:
            pass
        else:
            for key, value in band_expressions.items():
                print(key, value)
                band_math_image = self.imagery.expression(value).rename(key)
                expressions_image = expressions_image.addBands(band_math_image)
        
        ### gaussian smoothing
        gaussianKernel = ee.Kernel.gaussian(
        radius = 3,
        units = 'pixels'
        )
        
        gaussian_smoothed = expressions_image.convolve(gaussianKernel)

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
        #dog_sharp = gaussian_smoothed.add(gaussian_smoothed.convolve(dog_kernel)) # the original dog_method
        dog_sharp = gaussian_smoothed.convolve(dog_kernel)
        dog_sharp = dog_sharp.clip(self.ee_object)

        return dog_sharp
    
class SnicSegmentation:
    def __init__(self, given_preprocessed):
        self.preprocessed_imagery = given_preprocessed
        #self.given_shapefile = given_shapefile
        #self.ee_object = geemap.shp_to_ee(self.given_shapefile)

    def segmentation_func(self, seed_spacing=5, snic_compactness=0, snic_connectivity=4, seed_grid_shape='hex'):
        """
        Creates a segmented image using the script shown in the GEE workshop video.
        May add the option to change the SNIC function settings
        """
        
        # Get the band names from the preprocessed imagery
        bands = self.preprocessed_imagery.bandNames().getInfo()
        print(f"Original bands: {bands}") # Debugging

        # Create a list of mean band names
        bands_means_list = [f'{band}_mean' for band in bands]
        print(f"Mean bands list: {bands_means_list}") # Debugging

        # Add 'clusters' to the mean bands list
        bands_means_list.append('clusters')
        print(f"Mean bands list with clusters: {bands_means_list}") # Debugging

        # Ensure the number of mean bands matches the original bands plus 'clusters'
        assert len(bands_means_list) == len(bands) + 1, "The number of mean bands should be original bands plus 'clusters'"

        # Seed grid for segmentation
        seeds = ee.Algorithms.Image.Segmentation.seedGrid(seed_spacing, seed_grid_shape)
        
        # Run SNIC on the regular square grid
        snic = ee.Algorithms.Image.Segmentation.SNIC(
            image=self.preprocessed_imagery,
            compactness=snic_compactness,
            connectivity=snic_connectivity,
            neighborhoodSize=2 * seed_spacing,
            seeds=seeds
        ).select(bands_means_list, bands + ['clusters'])  # Adjusting the selection parameters
        
        # Extract clusters and calculate additional properties
        clusters = snic.select('clusters')
        stdDev = self.preprocessed_imagery.addBands(clusters).reduceConnectedComponents(ee.Reducer.stdDev(), 'clusters', 256)
        area = ee.Image.pixelArea().addBands(clusters).reduceConnectedComponents(ee.Reducer.sum(), 'clusters', 256)
        minMax = clusters.reduceNeighborhood(ee.Reducer.minMax(), ee.Kernel.square(1))
        perimeterPixels = minMax.select(0).neq(minMax.select(1)).rename('perimeter')
        perimeter = perimeterPixels.addBands(clusters).reduceConnectedComponents(ee.Reducer.sum(), 'clusters', 256)
        sizes = ee.Image.pixelLonLat().addBands(clusters).reduceConnectedComponents(ee.Reducer.minMax(), 'clusters', 256)
        width = sizes.select('longitude_max').subtract(sizes.select('longitude_min')).rename('width')
        height = sizes.select('latitude_max').subtract(sizes.select('latitude_min')).rename('height')
        
        # Combine all segmented properties
        segmented_properties = ee.Image.cat([
            snic.select(bands),
            stdDev,
            area,
            perimeter,
            width,
            height
        ]).float()  # .clip(self.ee_object)

        return segmented_properties


        
        

"""
def naip_savi_endvi(given_image):
    func_img = given_image
    
    # savi
    savi_exp = '((1 + 0.6) * (b("N") - b("R"))) / (b("N") + b("R") + 0.5)'
    savi = func_img.expression(savi_exp).rename('savi')
    func_img = func_img.addBands(savi)

    # endvi
    endvi_exp = '((b("N") + b("G")) - (2 * b("B"))) / ((b("N") + b("G")) + (2 + b("B")))'
    endvi = func_img.expression(endvi_exp).rename('endvi')
    func_final_img = func_img.addBands(endvi)
    
    return func_final_img 
"""






"""
def segmentation_func(stdrd_image, seed_spacing = 5, snic_compactness = 0, snic_connectivity = 4, seed_grid_shape = 'hex'):
    
    Creates a segmented image using the script shown in the GEE workshop video.
    May add the option to change the SNIC function settings
    standardized = stdrd_image
    gauss = gauss_smooth_func(standardized)
    gauss = dog_sharp(gauss)
    
    bands = ['R', 'G', 'B', 'N', 'savi', 'endvi']
    # seed_spacing default is now 5
    # seed_grid_shape now defaults to 'hex'
    seeds = ee.Algorithms.Image.Segmentation.seedGrid(seed_spacing, seed_grid_shape)
    
    # Run SNIC on the regular square grid.
    snic = ee.Algorithms.Image.Segmentation.SNIC(
      image = gauss,
      #size = 4, # shouldn't matter since have seed image
      compactness = snic_compactness, # spatial weighting not taken into account at 0. More compact at higher values
      connectivity = snic_connectivity, # 4 or 8
      neighborhoodSize = 2 * seed_spacing,
      seeds = seeds # the "seedGrid" given
    ).select(['R_mean', 'G_mean', 'B_mean', 'N_mean', 'savi_mean', 'endvi_mean', 'clusters'], 
             ['R', 'G', 'B', 'N', 'savi', 'endvi', 'clusters'])
    
    clusters = snic.select('clusters')
    stdDev = gauss.addBands(clusters).reduceConnectedComponents(ee.Reducer.stdDev(), 'clusters', 256)
    area = ee.Image.pixelArea().addBands(clusters).reduceConnectedComponents(ee.Reducer.sum(), 'clusters', 256)
    minMax = clusters.reduceNeighborhood(ee.Reducer.minMax(), ee.Kernel.square(1))
    perimeterPixels = minMax.select(0).neq(minMax.select(1)).rename('perimeter')
    perimeter = perimeterPixels.addBands(clusters) \
        .reduceConnectedComponents(ee.Reducer.sum(), 'clusters', 256)
    sizes = ee.Image.pixelLonLat().addBands(clusters).reduceConnectedComponents(ee.Reducer.minMax(), 'clusters', 256)
    width = sizes.select('longitude_max').subtract(sizes.select('longitude_min')).rename('width')
    height = sizes.select('latitude_max').subtract(sizes.select('latitude_min')).rename('height')
    objectPropertiesImage = ee.Image.cat([
      snic.select(bands),
      stdDev,
      area,
      perimeter,
      width,
      height
    ]).float()
    return objectPropertiesImage
"""

"""
### Using as reference for how to pull the bands
if segmented_as_bands == True:
    cluster_result = objectPropertiesImage.cluster(clusterer)
    cluster_properties = ['stdDev','area','perimeter','width','height']
    # will need to add a way to automatically pull the bands means. 
    #Can prob use a regex function to search the a generated list for things that end with '_means'
    band_list.extend(cluster_properties)
    # In this case I want to select the properties of each cluster and append them.
    # May need to add 'clusters' back as one of the bands
    cluster_prop = objectPropertiesImage.select(band_list)
    cluster_result.append(cluster_prop)
    return cluster_result
"""