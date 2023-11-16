###ee_install()

#library(rgee)
#library(rgeeExtra)
#library(reticulate)

# Initialize Earth Engine and GD
#ee_Initialize(drive=TRUE)


library(sf)
library(sp)
library(geojsonsf)
library(rlist)
# read in each geojson


files_list <- list.files(path="C:/Users/Justin/Desktop/mesquite/mesq_jsons")

# creating a path for each item in a file
file_address_func <- function(file_given) {
  addresses <- list()
  
  for (file in file_given) {
    address <- "C:/Users/Justin/Desktop/mesquite/mesq_jsons/"
    full_address <- paste0(address, file)
    length_list <- length(addresses)
    addresses <- append(addresses, full_address, after = length_list)
  }
  return(addresses)
}

listy <- file_address_func(files_list)
#listy



# generating names for each object to assign an sf value
object_names <- function(given_list) {
  ob_list <- list()
  
  for (listicle in given_list) {
    temp_string <- "buff"
    ob_name <- paste0(listicle, temp_string)
    length_list <- length(ob_list)
    ob_list <- append(ob_list, ob_name, after = length_list)
    
  }
  return(ob_list)
}

ob_names <- object_names(files_list)
#ob_names



# creating a function to save all the geojsons to sf objects
rng <- 1:length(listy)
geo_json_func <- function(given_list, given_range) {
  json_sf_list <- list()
  
  for (item in given_range) {
    full_address <- given_list[[item]]
    len_list <- length(json_sf_list)
    json_sf_list <- append(json_sf_list, geojson_sf(full_address), after = length(json_sf_list))
  }
  return(json_sf_list)
}  
json_list <- geo_json_func(listy, rng)
json_list[[1]]


# adding sf objects as ee assets
ee_list_func <- function(given_json_list, given_range) {
  eeItemList <- list()
  
  for (item in given_range) {
    eeItemList <- append(eeItemList,
                         sf_as_ee(
                           x = json_list[[item]],
                           assetID = ob_names[[item]]
                         ),
                         after = length(eeItemList)
    )
    
  }
  return(eeItemList)
}

eeItemList <- ee_list_func(json_list, rng)
#eeItemList




### change the feature collection to your boundary asset location
shp <- eeItemList[[10]] # change per buffer

### choose your imagery and the dates for it
year <- ee$ImageCollection('USDA/NAIP/DOQQ') %>%
  ee$ImageCollection$filterDate(ee$Date('2014-01-01'), 
                                ee$Date('2014-12-31')) %>%
  ee$ImageCollection$filterBounds(shp)

# mosaic the collection into a single image
year <- year$mosaic()

### clipping to shape
clip <- year$clip(shp)
###

### visibility parameters for the color image
visParam <- list(bands <- c('R', 'G', 'B'),
                 gamma = 1
)

# centering and adding to map to check that it's visualizing properly
#Map$centerObject(shp)
#Map$addLayer(clip, visParams= visParam)



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


######## Visualize if wanted ################
#visParamNorm <- list(bands <- c('R', 'G', 'B'),
#  min= 0,
#  max= 255
#  )

# Map$addLayer(normalized, visParams = visParamNorm)
###




#Doesn't work for NM 2009 -- see "check bands"
#band_names <- normalized$bandNames()
#print(band_names$get(4)$getInfo())

rgb_vari <- function(image_given) {
  image_bands <- image_given$select(c("R", "G", "B"))
  image <- image_bands
  
  vari <- image$expression(
    expression = '(G - R) / (G + R - B)',
    opt_map =  list(
      'G' = image$select('G'),
      'R' = image$select('R'),
      'B' = image$select('B')
    )
  )$rename('vari')
  return(vari)
}

#vari <- rgb_vari(normalized)

# adding vari as a band to use
#normalized <- normalized$addBands(vari)

# checking was added
#band_names <- normalized$bandNames()
#print(band_names$get(4)$getInfo()) 




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

# checking was added
band_names <- normalized$bandNames()
#print(band_names$get(4)$getInfo()) 



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

# checking was added
band_names <- normalized$bandNames()
#print(band_names$get(5)$getInfo()) 




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

visParamGauss <- list(bands <- c('R', 'G', 'B'),
                      min= 0,
                      max= 255
)

### checking that image was smoothed
#Map$addLayer(gauss, visParams = visParamGauss)




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





