import ee
import geemap



def segmentation_attributes(given_image, 
                            seed_spacing=5, snic_compactness=0, 
                            snic_connectivity=4, seed_grid_shape='hex'):
    """
    Creates a segmented image using the script shown in the GEE workshop video returns
    the properties of each segment for use with classification algorithms.
    """
    
    # Get the band names from the preprocessed imagery
    bands = given_image.bandNames().getInfo()
    #print(f"Original bands: {bands}") # Debugging

    # Create a list of mean band names
    bands_means_list = [f'{band}_mean' for band in bands]
    #print(f"Mean bands list: {bands_means_list}") # Debugging

    # Add 'clusters' to the mean bands list
    bands_means_list.append('clusters')
    #print(f"Mean bands list with clusters: {bands_means_list}") # Debugging

    # Ensure the number of mean bands matches the original bands plus 'clusters'
    assert len(bands_means_list) == len(bands) + 1, "The number of mean bands should be original bands plus 'clusters'"

    # Seed grid for segmentation
    seeds = ee.Algorithms.Image.Segmentation.seedGrid(seed_spacing, seed_grid_shape)
    
    # Run SNIC on the regular square grid
    snic = ee.Algorithms.Image.Segmentation.SNIC(
        image=given_image,
        compactness=snic_compactness,
        connectivity=snic_connectivity,
        neighborhoodSize=2 * seed_spacing,
        seeds=seeds
    ).select(bands_means_list, bands + ['clusters'])  # Adjusting the selection parameters
    
    # Extract clusters and calculate additional properties
    clusters = snic.select('clusters')
    stdDev = given_image.addBands(clusters).reduceConnectedComponents(ee.Reducer.stdDev(), 'clusters', 256)
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
    #print(segmented_properties.bandNames().getInfo())
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