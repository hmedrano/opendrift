# This file is part of OpenDrift.
#
# OpenDrift is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2
#
# OpenDrift is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenDrift.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Knut-Frode Dagestad, MET Norway
#
# Added by Favio Medrano hmedrano@cicese.mx, Feb 2017
#

import logging
from bisect import bisect_left, bisect_right

import numpy as np
from netCDF4 import Dataset, MFDataset, num2date

from opendrift.readers.basereader import BaseReader, vector_pairs_xy



class Reader(BaseReader):

    def __init__(self, filename=None, name=None, gridfile=None, custom_var_mapping=None):

        if filename is None:
            raise ValueError('Need filename as argument to constructor')

        # Map NEMO variable names to CF standard_name
        self.NEMO_variable_mapping = {        
            'sossheig': 'sea_surface_height',    # sea_surface_above_geoid
            'vozocrtx': 'x_sea_water_velocity',  
            'vomecrty': 'y_sea_water_velocity',
            'vovecrtz': 'upward_sea_water_velocity',
            'votemper': 'sea_water_temperature', # sea_water_potential_temperature
            'vosaline': 'sea_water_salinity',            
            'utau': 'surface_downward_x_stress',
            'vtau': 'surface_downward_y_stress', }
            
        if custom_var_mapping is not None:
            for var_name in list(self.NEMO_variable_mapping.keys()):                
                for cvar_name in custom_var_mapping.keys():                
                    if custom_var_mapping[cvar_name] == self.NEMO_variable_mapping[var_name]:
                        self.NEMO_variable_mapping.pop(var_name)
                        break
            self.NEMO_variable_mapping.update(custom_var_mapping)     

        filestr = str(filename)
        if name is None:
            self.name = filestr
        else:
            self.name = name

        try:
            # Open file, check that everything is ok
            logging.info('Opening dataset: ' + filestr)
            if ('*' in filestr) or ('?' in filestr) or ('[' in filestr):
                logging.info('Opening files with MFDataset')
                self.Dataset = MFDataset(filename)
            else:
                logging.info('Opening file with Dataset')
                self.Dataset = Dataset(filename, 'r')
        except Exception as e:
            raise ValueError(e)
  
        if 'deptht' in self.Dataset.variables or 'depth' in self.Dataset.variables:
            # Read depth values
            try:
                varz = self.Dataset.variables['deptht']
            except:
                varz = self.Dataset.variables['depth']

            if 'positive' not in varz.ncattrs() or \
                    varz.__dict__['positive'] == 'up':
                self.z = varz[:]
            else:
                self.z = -varz[:]

        if 'nav_lat' in self.Dataset.variables:
            # Horizontal cordinates and directions
            self.lat = self.Dataset.variables['nav_lat'][:]
            self.lon = self.Dataset.variables['nav_lon'][:]
        else:
            if gridfile is None:
                raise ValueError(filename + ' does not contain lon/lat '
                                 'arrays, please supply a grid-file '
                                 '"gridfile=<grid_file>"')
            else:
                gf = Dataset(gridfile)
                self.lat = gf.variables['nav_lat'][:]
                self.lon = gf.variables['nav_lon'][:]

        # Get time coverage        
        ocean_time = self.Dataset.variables['time_counter']        
        time_units = ocean_time.__dict__['units']
        self.times = num2date(ocean_time[:], time_units)
        self.start_time = self.times[0]
        self.end_time = self.times[-1]
        if len(self.times) > 1:
            self.time_step = self.times[1] - self.times[0]
        else:
            self.time_step = None

        # x and y are rows and columns for unprojected datasets
        self.xmin = 0.
        self.xmax = np.float(len(self.Dataset.dimensions['x'])) - 1
        self.delta_x = 1.
        self.ymin = 0.
        self.ymax = np.float(len(self.Dataset.dimensions['y'])) - 1
        self.delta_y = 1.  
        self.name = 'nemo native'

        # Find all variables having standard_name
        self.variables = []
        for var_name in self.Dataset.variables:
            if var_name in self.NEMO_variable_mapping.keys():
                var = self.Dataset.variables[var_name]
                self.variables.append(self.NEMO_variable_mapping[var_name])
        logging.debug('reader variables : ' + str(self.variables) )
        # Run constructor of parent Reader class
        super(Reader, self).__init__()

    def get_variables(self, requested_variables, time=None,
                      x=None, y=None, z=None, block=False):
        
        requested_variables, time, x, y, z, outside = self.check_arguments(
            requested_variables, time, x, y, z)

        nearestTime, dummy1, dummy2, indxTime, dummy3, dummy4 = \
            self.nearest_time(time)

        variables = {}

        if hasattr(self, 'z') and (z is not None):
            # Find z-index range
            # NB: may need to flip if self.z is ascending
            indices = np.searchsorted(-self.z, [-z.min(), -z.max()])
            indz = np.arange(np.maximum(0, indices.min() - 1 -
                                        self.verticalbuffer),
                             np.minimum(len(self.z), indices.max() + 1 +
                                        self.verticalbuffer))
            if len(indz) == 1:
                indz = indz[0]  # Extract integer to read only one layer
        else:
            indz = 0

        # Find horizontal indices corresponding to requested x and y
        indx = np.floor((x-self.xmin)/self.delta_x).astype(int)
        indy = np.floor((y-self.ymin)/self.delta_y).astype(int)
        indx[outside] = 0  # To be masked later
        indy[outside] = 0
        indx_el = indx
        indy_el = indy
        if block is True:
            # Adding buffer, to cover also future positions of elements
            buffer = self.buffer
            indx = np.arange(np.max([0, indx.min()-buffer]),
                             np.min([indx.max()+buffer, self.lon.shape[1]]))
            indy = np.arange(np.max([0, indy.min()-buffer]),
                             np.min([indy.max()+buffer, self.lon.shape[0]]))                             


        for par in requested_variables:
            varname = [name for name, cf in
                       self.NEMO_variable_mapping.items() if cf == par]
            var = self.Dataset.variables[varname[0]]                 

            # Automatic masking may lead to trouble for NEMO files
            var.set_auto_maskandscale(False)

            try:
                FillValue = getattr(var, '_FillValue')
            except:
                FillValue = None            
            try:
                scale = getattr(var, 'scale_factor')
            except:
                scale = 1
            try:
                offset = getattr(var, 'add_offset')
            except:
                offset = 0                

            continous = True # Can the request not be continous?
            ensemble_dim = None
            if continous is True:
                if var.ndim == 2:
                    variables[par] = var[indy, indx]
                elif var.ndim == 3:
                    variables[par] = var[indxTime, indy, indx]
                elif var.ndim == 4:                    
                    variables[par] = var[indxTime, indz, indy, indx]
                else:
                    raise Exception('Wrong dimension of variable: ' +
                                    self.variable_mapping[par])
            else:  # We need to read left and right parts separately
                if var.ndim == 2:
                    left = var[indy, indx_left]
                    right = var[indy, indx_right]
                    variables[par] = np.ma.concatenate((left, right), 1)
                elif var.ndim == 3:
                    left = var[indxTime, indy, indx_left]
                    right = var[indxTime, indy, indx_right]
                    variables[par] = np.ma.concatenate((left, right), 1)
                elif var.ndim == 4:
                    left = var[indxTime, indz, indy, indx_left]
                    right = var[indxTime, indz, indy, indx_right]
                    variables[par] = np.ma.concatenate((left, right), 2)

            # Manual scaling, offsetting and masking due to issue with NEMO files
            logging.debug('Manually masking %s, FillValue %s, scale %s, offset %s' % 
                (par, FillValue, scale, offset))
            if FillValue is not None:
                if var.dtype != FillValue.dtype:
                    mask = variables[par] == 0
                    if not 'already_warned' in locals():
                        logging.warning('Data type of variable (%s) and _FillValue (%s) is not the same. Masking 0-values instead' % (var.dtype, FillValue.dtype))
                        already_warned = True
                else:
                    logging.warning('Masking ' + str(FillValue))
                    mask = variables[par] == FillValue   
            variables[par] = variables[par]*scale + offset
            if FillValue is not None:
                variables[par][mask] = np.nan                 

            # If 2D array is returned due to the fancy slicing
            # methods of netcdf-python, we need to take the diagonal
            if variables[par].ndim > 1 and block is False:
                variables[par] = variables[par].diagonal()

            # Mask values outside domain
            variables[par] = np.ma.array(variables[par],
                                         ndmin=2, mask=False)
            if block is False:
                variables[par].mask[outside] = True

            # Mask extreme values which might have slipped through
            variables[par] = np.ma.masked_outside(
                variables[par], -30000, 30000)

            # Ensemble blocks are split into lists
            if ensemble_dim is not None:
                num_ensembles = variables[par].shape[ensemble_dim]
                logging.debug('Num ensembles: %i ' % num_ensembles)
                newvar = [0]*num_ensembles
                for ensemble_num in range(num_ensembles):
                    newvar[ensemble_num] = \
                        np.take(variables[par],
                                ensemble_num, ensemble_dim)
                variables[par] = newvar

        # Store coordinates of returned points
        try:
            variables['z'] = self.z[indz]
        except:
            variables['z'] = None   

        if block is True:
            # TODO: should be midpoints, but angle array below needs integer
            #indx = indx[0:-1]  # Only if de-staggering has been performed
            #indy = indy[1::]
            variables['x'] = indx
            variables['y'] = indy
        else:
            variables['x'] = self.xmin + (indx-1)*self.delta_x
            variables['y'] = self.ymin + (indy-1)*self.delta_y

        variables['x'] = variables['x'].astype(np.float)
        variables['y'] = variables['y'].astype(np.float)
        variables['time'] = nearestTime

        # Masking NaN
        #for var in requested_variables:
        #    variables[var] = np.ma.masked_invalid(variables[var])

        #print(variables.keys()) ; 
        return variables

