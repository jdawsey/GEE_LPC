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

def smoothing_func(given_image):
    ### gaussian smoothing
    gaussianKernel = ee.Kernel.gaussian(
      radius = 3,
      units = 'pixels'
    )
    
    gaussian_smooth = given_image.convolve(gaussianKernel)
    
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
    gauss = gaussian_smooth.add(given_image.convolve(dog)) 
    return gauss