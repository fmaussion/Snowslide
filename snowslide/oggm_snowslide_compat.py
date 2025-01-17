""" this module is a task as defined in OGGM. It allows the use of snowslide combined with OGGM workflow
"""

# Module logger
import logging
log = logging.getLogger(__name__)

from oggm import cfg
from oggm import tasks, utils, workflow, graphics
from oggm.core import massbalance
import numpy as np
import pandas as pd
import xarray as xr
import os
import matplotlib.pyplot as plt

from snowslide.snowslide_main import snowslide_base

@utils.entity_task(log, writes=['gridded_data'])
def snowslide_to_gdir(gdir,routing='mfd'):
    """ Add an ideal estimation of avalanches snow redistribution to this glacier directory
    
    Parameters
    ----------
    gdir : :py:class:`oggm.GlacierDirectory`
        the glacier directory to process
    SND_init : float
        Idealised initial snow depth chosen to run the Snowslide simulation
    """
    # Get the path to the gridded data file and open it 
    gridded_data_path = gdir.get_filepath('gridded_data')
    with xr.open_dataset(gridded_data_path) as ds:
        ds = ds.load()

    # Get the path of the dem and climate data
    path_to_dem = gdir.get_filepath('dem')
   #path_to_climate = gdir.get_filepath('climate_historical') --> For an non ideal version of snowslide

    # Launch snowslide simulation with idealized 1m initial snow depth
    SND0 = np.full(np.shape(ds.topo),float(1.0))
    param_routing={"routing":routing,"preprocessing":True}
    SND = snowslide_base(path_to_dem,SND0=SND0,param_routing=param_routing)    

    # Write
    with utils.ncDataset(gdir.get_filepath('gridded_data'), 'a') as nc:

        vn = 'snowslide_1m'
        if vn in nc.variables:
            v = nc.variables[vn]
        else:
            v = nc.createVariable(vn, 'f4', ('y', 'x', ), zlib=True)
        
        v.units = 'm'
        ln = 'Snowcover after avalanches'
        v.long_name = ln
        v[:] = SND

@utils.entity_task(log)
def snowslide_statistics(gdir):
    """ Gather statistics about the Snowslide snow redistribution
    """
    resolution = abs(gdir.grid.dx)
    d = dict()
    # Easy stats - this should always be possible
    d['rgi_id'] = gdir.rgi_id
    d['rgi_region'] = gdir.rgi_region
    d['rgi_subregion'] = gdir.rgi_subregion
    d['rgi_area_km2'] = gdir.rgi_area_km2
    d['snowslide_1m_glacier_average'] = np.NaN
    d['snowslide_deposit_area'] = np.NaN
    d['snowslide_deposit_volume'] = np.NaN

    try:
        with xr.open_dataset(gdir.get_filepath('gridded_data')) as ds:
            map_result = ds['snowslide_1m'].where(ds['glacier_mask'], np.NaN).load()
            d['snowslide_1m_glacier_average'] = map_result.mean().data
            d['snowslide_deposit_area'] = float(map_result.where(map_result==1,drop=True).count()) * resolution**2
            d['snowslide_deposit_volume'] = float(map_result.where(map_result==1,drop=True).count()) * resolution**2
    except (FileNotFoundError, AttributeError, KeyError):
        pass

    return d


@utils.global_task(log)
def compile_snowslide_statistics(gdirs, filesuffix='', path=True):
    """Gather as much statistics as possible about a list of glaciers.

    It can be used to do result diagnostics and other stuffs.

    Parameters
    ----------
    gdirs : list of :py:class:`oggm.GlacierDirectory` objects
        the glacier directories to process
    filesuffix : str
        add suffix to output file
    path : str, bool
        Set to "True" in order  to store the info in the working directory
        Set to a path to store the file to your chosen location
    """
    from oggm.workflow import execute_entity_task

    out_df = execute_entity_task(snowslide_statistics, gdirs)

    out = pd.DataFrame(out_df).set_index('rgi_id')

    if path:
        if path is True:
            out.to_csv(os.path.join(cfg.PATHS['working_dir'],
                                    ('snowslide_statistics' +
                                     filesuffix + '.csv')))
        else:
            out.to_csv(path)

    return out