import os
import ee
import geemap

def file_address_func(file_dir_given):
    file_path = os.listdir(file_dir_given)
    addresses = []
    for file in file_path:
        address = file_dir_given + "/"
        full_address = address + file
        length_list = len(addresses)
        addresses.append(full_address)
    return addresses


def ee_list_func(given_json_list):
    rng = range(len(given_json_list))
    ee_item_list = []

    for item in rng:
        ee_item_list.append(geemap.geojson_to_ee(given_json_list[item]))
    
    return ee_item_list

def naip_savi(given_image):
    func_img = given_image
    
    # savi
    savi_exp = '((1 + 0.6) * (b("N") - b("R"))) / (b("N") + b("R") + 0.5)'
    savi = func_img.expression(savi_exp).rename('savi')
    func_final_img = func_img.addBands(savi)
    
    return func_final_img 

def stdrd_func(given_image, given_geo):
    func_img = given_image
    st_bandNames = func_img.bandNames()
    meanDict = func_img.reduceRegion(
      reducer = ee.Reducer.mean(),
      geometry = given_geo,
      scale = 1,
      maxPixels = 200000000,
      bestEffort = True,
      tileScale = 16
    )
    means = ee.Image.constant(meanDict.values(st_bandNames))
    centered = func_img.subtract(means)

    stdDevDict = func_img.reduceRegion(
      reducer = ee.Reducer.stdDev(),
      geometry = given_geo,
      scale = 1,
      maxPixels = 200000000,
      bestEffort = True,
      tileScale = 16
    )

    stddevs = ee.Image.constant(stdDevDict.values(st_bandNames))
    standardized = centered.divide(stddevs)
    return standardized

def gauss_smooth_func(given_image):
    ### gaussian smoothing
    gaussianKernel = ee.Kernel.gaussian(
      radius = 3,
      units = 'pixels'
    )
    
    gaussian_smooth = given_image.convolve(gaussianKernel)
    return gaussian_smooth

def dog_sharp(given_image):
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
    
    dog = fat.add(skinny)
    #changed name from sharpened
    dog_fin = given_image.add(given_image.convolve(dog)) 
    return dog_fin

def stdrd_ref_func(ee_item_list, given_geometry):
    ee_items = ee_item_list
    poly_num = given_geometry
    shp = ee_items[poly_num] # list
    
    year = ee.ImageCollection('USDA/NAIP/DOQQ').filterDate('2016-01-01', '2016-12-31').filterBounds(shp)
    
    year = year.mosaic() # mosaicing so that becomes a single image that can be worked with
    clip = year.clip(shp) # clip to the polygon bounds
    
    n_clip = naip_savi(clip)
    standardized = stdrd_func(n_clip, shp)
    return standardized

def segmentation_func(ee_item_list, given_geometry, stdrd_image):
    standardized = stdrd_image
    gauss = gauss_smooth_func(standardized)
    gauss = dog_sharp(gauss)
    
    bands = ['R', 'G', 'B', 'N', 'savi']
    seed_spacing = 5
    seeds = ee.Algorithms.Image.Segmentation.seedGrid(seed_spacing, 'hex')
    
    # Run SNIC on the regular square grid.
    snic = ee.Algorithms.Image.Segmentation.SNIC(
      image = gauss,
      #size = 4, # shouldn't matter since have seed image
      compactness = 0, # spatial weighting not taken into account at 0. More compact at higher values
      connectivity = 8, # 4 or 8
      neighborhoodSize = 2 * seed_spacing,
      seeds = seeds # the "seedGrid" given
    ).select(['R_mean', 'G_mean', 'B_mean', 'N_mean', 'savi_mean', 'clusters'], ['R', 'G', 'B', 'N', 'savi', 'clusters'])
    
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

def obj_class(ee_item_given, poly_num, given_segmented, max_clusters):
    objectPropertiesImage = given_segmented
    shp = ee_item_given[poly_num]
    
    training = objectPropertiesImage.sample(
      region = shp,
      scale = 1, #change depending on year
      numPixels = 10000
    )
    
    ### the actual classification function
    clusterer = ee.Clusterer.wekaXMeans(maxClusters = max_clusters, # change clusters depending on imagery
                                        maxIterations = 5, 
                                        useKD = True).train(training)
    
    result = objectPropertiesImage.cluster(clusterer)
    return result




def pb_class(ee_item_list, given_geometry, stdrd_image, max_clusters):
    standardized = stdrd_image
    shp = ee_item_list[given_geometry]
    
    gauss = gauss_smooth_func(standardized)
    gauss = dog_sharp(gauss)
    
    pb_training = gauss.sample(
      region = shp,
      scale = 1, #change depending on year
      numPixels = 10000
    )
    pb_clusterer = ee.Clusterer.wekaXMeans(maxClusters = max_clusters, # change clusters depending on imagery
                                        maxIterations = 5, 
                                        useKD = True).train(pb_training)
    
    pixel_based_result = gauss.cluster(pb_clusterer)
    return pixel_based_result

def pasture_visualizer(ee_item_list, given_geometry, stdrd_image, seed_space, grid_type):
    standardized = stdrd_image
    gauss = gauss_smooth_func(standardized)
    gauss = dog_sharp(gauss)
    
    bands = ['R', 'G', 'B', 'N', 'savi']
    seed_spacing = seed_space
    seeds = ee.Algorithms.Image.Segmentation.seedGrid(seed_spacing, grid_type)
    
    # Run SNIC on the regular square grid.
    snic = ee.Algorithms.Image.Segmentation.SNIC(
      image = gauss,
      #size = 4, # shouldn't matter since have seed image
      compactness = 0, # spatial weighting not taken into account at 0. More compact at higher values
      connectivity = 8, # 4 or 8
      neighborhoodSize = 2 * seed_spacing,
      seeds = seeds # the "seedGrid" given
    ).select(['R_mean', 'G_mean', 'B_mean', 'N_mean', 'savi_mean', 'clusters'], ['R', 'G', 'B', 'N', 'savi', 'clusters'])
    
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