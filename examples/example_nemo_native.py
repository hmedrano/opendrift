#!/usr/bin/env python

from datetime import datetime, timedelta

from opendrift.readers import reader_basemap_landmask
from opendrift.readers import reader_netCDF_CF_generic
from opendrift.readers import reader_NEMO_native
from opendrift.models.openoil import OpenOil


o = OpenOil(loglevel=0)  # Set loglevel to 0 for debug information

# Datos corrida nemo golfo36-agr02
# reader_nemo = reader_NEMO_native.Reader('http://c60:8080/thredds/dodsC/nemogolfo36agr02/2007gridtuv')
# reader_nemo = reader_NEMO_native.Reader('http://dataserver.cigom.org/thredds/dodsC/linea3/phy/nemo-agr02-physics-2007-2011/gridTuvw')
# Datos vientes dfs52 1979 - 2015
# reader_winds = reader_netCDF_CF_generic.Reader('http://c60:8080/thredds/dodsC/dfs52/u10v10')
#reader_winds = reader_netCDF_CF_generic.Reader('http://dataserver.cigom.org/thredds/dodsC/linea3/phy/dfs52/u10v10')

# Gulf Mexico Xkm
#reader_nemo = reader_NEMO_native.Reader(o.test_data_folder() +
#    'Dec2009_GulfMexico_nemo_singlefileTUV/gulfmexico-gridT.nc')

reader_glorys = reader_NEMO_native.Reader('http://chaman.cicese.mx/thredds/dodsC/glorys2v4/gridtuv') 

#reader_nemo = reader_NEMO_native.Reader('https://sener:sener2016@cic-pem.cicese.mx/thredds/dodsC/hidrocarburos/linea3/climatologias/nemo-golfo-36',
#                                         custom_var_mapping={'vozocrtx_X' : 'x_sea_water_velocity', 'vomecrty_Y' : 'y_sea_water_velocity'})

# Landmask (Basemap)
# reader_basemap = reader_basemap_landmask.Reader(
#                     llcrnrlon=-98.40654, llcrnrlat=14.18613,
#                     urcrnrlon=-78.57984, urcrnrlat=30.70805, resolution='i')

# Add readers, ..
#o.add_reader([reader_basemap, reader_nemo, reader_winds])
#o.add_reader([reader_basemap, reader_nemo])
#o.add_reader([reader_basemap, reader_glorys])
o.add_reader([reader_glorys])

simulation_days=31

# Particulas perdido area 
lon = -95.64; lat = 24.67  
starttime = datetime(2009, 12, 1, 12)  
time = [starttime, starttime + timedelta(hours=24*simulation_days)]
o.seed_elements(lon, lat, radius=10, number=2000, time=time, z=-0.50576001)  # El Valor de z es importante pues por default usa 0 y nemo su primer valor de prof es -0.50576001

# Run model
print (o)
o.run(duration=timedelta(days=simulation_days),
      time_step=timedelta(hours=12),
      time_step_output=timedelta(days=1))

# Print and plot results
o.plot(linecolor="age_seconds")
o.plot(background=["x_sea_water_velocity","y_sea_water_velocity"])
o.animation(background=["x_sea_water_velocity","y_sea_water_velocity"])
