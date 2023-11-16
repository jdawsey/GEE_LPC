###ee_install()

library(rgee)
library(rgeeExtra)
library(reticulate)

# Initialize Earth Engine and GD
ee_Initialize()
ee_Initialize(drive=TRUE)


library(sf)
library(sp)
library(geojsonsf)
library(rlist)
library(geojsonio)
# read in each geojson





quick_classify <- function (given_ee_item, start_date_given, end_date_given) {
  shp <- given_ee_item # change per buffer
  
  ### choose your imagery and the dates for it
  year <- ee$ImageCollection('USDA/NAIP/DOQQ') %>%
    ee$ImageCollection$filterDate(ee$Date(start_date_given), 
                                  ee$Date(end_date_given)) %>%
    ee$ImageCollection$filterBounds(shp)
  
  # mosaic the collection into a single image
  year <- year$mosaic()
  
  ### clipping to shape
  clip <- year$clip(shp)
  ###
  
  
  
  # Get mean and SD in every band by combining reducers.
  stats <- clip$reduceRegion(
    reducer = ee$Reducer$mean()$combine(
      reducer2 = ee$Reducer$stdDev(),
      sharedInputs = TRUE
    ),
    geometry = shp,
    scale = 1, # change depending on year
    bestEffort = TRUE # Use maxPixels if you care about scale.
  )
  
  #print(stats$getInfo())
  
  # Extract means and SDs to images.
  meansImage <- stats$toImage()$select('.*_mean')
  sdsImage <- stats$toImage()$select('.*_stdDev')
  coeffVarImage <- meansImage$divide(sdsImage)
  
  normalized = clip$subtract(coeffVarImage)
  
  
  
  
  
  
  rgb_savi <- function(image_given) {
    image_bands <- image_given$select(c("R", "N"))
    image <- image_bands
    
    savi <- image$expression(
      expression = '(1 + 0.6) * (N - R) / (N + R + 0.6)',
      opt_map =  list(
        'R' = image$select('R'),
        'N' = image$select('N')
      )
    )$rename('savi')
    return(savi)
  }
  
  savi <- rgb_savi(normalized)
  
  # adding savi as a band to use
  normalized <- normalized$addBands(savi)
  
  
  
  
  
  rgb_endvi <- function(image_given) {
    image_bands <- image_given$select(c("N", "G", "B"))
    image <- image_bands
    
    endvi <- image$expression(
      expression = '((N + G) - (2 * B)) / ((N + G) + (2 + B))',
      opt_map =  list(
        'N' = image$select('N'),  
        'G' = image$select('G'),
        'B' = image$select('B')
      )
    )$rename('endvi')
    return(endvi)
  }
  
  endvi <- rgb_endvi(normalized)
  
  # adding endvi as a band to use
  normalized <- normalized$addBands(endvi)
  
  
  
  
  
  # Get mean and SD in every band by combining reducers.
  stats <- normalized$reduceRegion(
    reducer = ee$Reducer$mean()$combine(
      reducer2 = ee$Reducer$stdDev(),
      sharedInputs = TRUE
    ),
    geometry = shp,
    scale = 1, # change depending on year
    bestEffort = TRUE # Use maxPixels if you care about scale.
  )
  
  #print(stats$getInfo())
  
  # Extract means and SDs to images.
  meansImage <- stats$toImage()$select('.*_mean')
  sdsImage <- stats$toImage()$select('.*_stdDev')
  coeffVarImage <- meansImage$divide(sdsImage)
  
  normalized = normalized$subtract(coeffVarImage)
  
  
  
  
  ### DoG sharpening
  fat <- ee$Kernel$gaussian(
    radius = 3,
    sigma = 3,
    magnitude = -1.0,
    units = 'pixels'
  )
  
  skinny <- ee$Kernel$gaussian(
    radius = 3,
    sigma = 0.5,
    units = 'pixels'
  )
  
  dog <- fat$add(skinny)
  sharpened <- normalized$add(normalized$convolve(dog))
  ###
  
  ### gaussian smoothing
  gaussianKernel <- ee$Kernel$gaussian(
    radius = 3,
    units = 'pixels'
  )
  
  gauss <- sharpened$convolve(gaussianKernel)
  ###
  
  
  
  
  
  ### creating training samples for the unsupervised classification
  training <- gauss$sample(
    region = shp,
    scale = 1, #change depending on year
    numPixels = 5000
  )
  ###
  
  ### the actual classification function
  clusterer <- ee$Clusterer$wekaKMeans(10) %>% # change clusters depending on imagery
    ee$Clusterer$train(training)
  
  result <- gauss$cluster(clusterer)
  ###
  
  
  
  
  return(result)
  
  
  
}


### change the feature collection to your boundary asset location
shp <- eeItemList[[10]] # change per buffer



drive_image <- ee_image_to_drive(
  image = normalized,
  description = "export",
  folder = "!imagery",
  region = shp,
  scale = 1,
  max = 130000000
)

drive_image$start()




#shp_geo <- shp$geometry()

drive_image <- ee_image_to_drive(
  image = result,
  description = "export",
  folder = "!imagery",
  region = shp,
  scale = 1,
  max = 130000000
)

drive_image$start()





naipNM_2009 <- ee_as_raster( #change name depending on raster to be downloaded
  image = result,
  region = shp_geo,
  dsn = "naipNM_2009.tif", # change for your own path.
  scale = 1,
)





