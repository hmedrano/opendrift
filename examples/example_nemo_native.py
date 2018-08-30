#!/usr/bin/env python

from datetime import datetime, timedelta

from opendrift.readers import reader_basemap_landmask
from opendrift.readers import reader_netCDF_CF_generic
from opendrift.readers import reader_NEMO_native
from opendrift.models.openoil import OpenOil


o = OpenOil(loglevel=0)  # Set loglevel to 0 for debug information

# Gulf of Mexico 1/12 degree
reader_nemo = reader_NEMO_native.Reader(o.test_data_folder() +
                                        '01Jan2006_GulfofMexico_z_3d/NATL3-JREF2.3_y2006m01_gridTuv.nc')

# Landmask (Basemap)
#reader_basemap = reader_basemap_landmask.Reader(
#                     llcrnrlon=-98.19, llcrnrlat=17.51,
#                     urcrnrlon=-78.86, urcrnrlat=30.50, resolution='i')

# Add readers
#o.add_reader([reader_basemap, reader_nemo])
o.add_reader([reader_nemo])

# Particles perdido area 
lon = -95.64; lat = 24.67  

simulation_days=30
starttime = datetime(2006, 1, 1)  
time = [starttime, starttime + timedelta(hours=24*simulation_days)]
o.seed_elements(lon, lat, radius=10, number=400, time=time, z=-1.50) 

# Run model
o.run(duration=timedelta(days=simulation_days),
      time_step=timedelta(hours=6),
      time_step_output=timedelta(hours=12))

# Plot results
o.animation() 
o.plot(linecolor="age_seconds")
o.plot(background=["x_sea_water_velocity","y_sea_water_velocity"])
#o.animation(background=["x_sea_water_velocity","y_sea_water_velocity"])
