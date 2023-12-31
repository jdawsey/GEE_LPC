library(languageserver)
library(jsonlite)
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


files_list <- list.files(path = "C:/Users/Justin Dawsey/Desktop/mesq_jsons") # user defined
file_path_for_function <- "C:/Users/Justin Dawsey/Desktop/mesq_jsons/"


# adding sf objects as ee assets
ee_list_func <- function(files_list_given, file_path_given) {
  
  eeItemList <- list()
  rng <- 1:length(files_list_given)
  file_pathy <- file_path_given
  
  # creating a path for each item in a file
  file_address_func <- function(files_given) {
    addresses <- list()
    
    for (file in files_given) {
      address <- file_pathy
      full_address <- paste0(address, file)
      length_list <- length(addresses)
      addresses <- append(addresses, full_address, after = length_list)
    }
    return(addresses)
  }
  #running function and saving to list for use with below functions
  listy <- file_address_func(files_list_given)
  #return(listy)
  
  
  
  object_names <- function(given_list) { #given_list = "files_list_given" in original function attribute
    ob_list <- list()
    
    for (listicle in given_list) {
      temp_string <- "buff"
      ob_name <- paste0(listicle, temp_string)
      length_list <- length(ob_list)
      ob_list <- append(ob_list, ob_name, after = length_list)
      
    }
    return(ob_list)
  }
  ob_names <- object_names(files_list_given)
  
  
  
  
  # creating a function to save all the geojsons to sf objects
  geo_json_func <- function(given_list) { #given_list = "listy on line above object names function creation
    json_sf_list <- list()
    
    for (item in rng) {
      full_address <- given_list[[item]] # testing changing brackets
      len_list <- length(json_sf_list)
      json_sf_list <- append(json_sf_list, geojson_sf(full_address), after = length(json_sf_list))
    }
    return(json_sf_list)
  }  
  
  json_list <- geo_json_func(listy)
  #return(json_list)
  
  # finally saving all as assets
  for (item in rng) {
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

eeItemList <- ee_list_func(files_list, file_path_for_function)
#eeItemList


#############################################################################
#############################################################################
#############################################################################
#############################################################################


quick_gaussed <- function (given_ee_item, start_date_given, end_date_given) {
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
  
  return(gauss)
}  


##########################################################################
##########################################################################
##########################################################################
##########################################################################

  
quick_classify <- function (gaussed_ee_item, region, num_clusters_wanted) {
  gauss <- gaussed_ee_item
  shp <- ee_item
  
  ### creating training samples for the unsupervised classification
  training <- gauss$sample(
    region = shp,
    scale = 1, #change depending on year
    numPixels = 5000
  )
  ###
  
  ### the actual classification function
  clusterer <- ee$Clusterer$wekaKMeans(num_clusters_wanted) %>% # change clusters depending on imagery
    ee$Clusterer$train(training)
  
  result <- gauss$cluster(clusterer)
  ###
  
  
  
  
  return(result)
}

##############################################################
##############################################################
##############################################################
##############################################################


start_date <- '2016-01-01'
end_date <- '2016-12-31'
ee_item <- eeItemList[[5]]

buff_gauss <- quick_gaussed(ee_item, start_date, end_date)
num_clusters <- 10
buff_classified <- quick_classify(buff_gauss, ee_item, num_clusters)



drive_image <- ee_image_to_drive(
  image = buff_normalized,
  description = "export",
  folder = "!imagery",
  region = eeItemList[[5]],
  scale = 1,
  max = 130000000
)

drive_image$start()




#shp_geo <- shp$geometry()

drive_image <- ee_image_to_drive(
  image = buff_classified,
  description = "export",
  folder = "",
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





