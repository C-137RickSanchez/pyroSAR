import os
import socket
from scoop import futures

from pyroSAR.S1 import OSV
from pyroSAR.snap import geocode
from pyroSAR.spatial import vector
from swos.testsites import lookup

from pyroSAR import Archive
from pyroSAR.ancillary import finder

"""
This script is an example usage for processing Sentinel-1 scenes with SNAP

Run this script by calling the 'start_gamma.sh' scipt.

The following tasks are performed:
- a directory is scanned for valid Sentinel-1 scenes
- the found scenes are ingested into a spatialite database
- orbit state vector (OSV) files are downloaded to a user-defined directory (these are needed for precise orbit information)
    - currently this is implemented to update a fixed directory in which all OSV files are stored
    - an empty directory will first be filled with all available OSV files on the server
- a cluster job is setup using package 'scoop', which assigns a list of testsites to different cluster nodes
- for each site:
    - query the SAR scenes, which overlap with your testsite and match certain criteria (e.g. sensor, acquisition mode etc.)
    - filter the selected scenes by thos that have already been processed and saved to the defined output directory
    - do parallelized processing using package 'pathos'
"""

# the sites to be processed
sites = ['Egypt_Burullus', 'France_Camargue', 'Kenya_Lorian_Olbolossat', 'Sweden_Skogaryd', 'Sweden_Store-Mosse']

# the pyroSAR database file
dbfile = '/geonfs01_vol1/ve39vem/swos_process/SWOS_scenelist.db'

# the main directory for storing the processed results
maindir = '/geonfs01_vol1/ve39vem/swos_process'


def worker(sitename):
    #######################################################################################
    # setup general processing parameters

    resolution = 20
    parallel1 = 6
    parallel2 = 6
    os.environ['OMP_NUM_THREADS'] = str(parallel2)
    #######################################################################################
    # get the maximum date of the precise orbit files
    # as type also 'RES' can be selected. These files are not as precise as POE and thus geocoding might not be
    # quite as accurate
    with OSV(osvdir_poe, osvdir_res) as osv:
        maxdate = osv.maxdate(type='POE', datetype='stop')
    #######################################################################################
    # define the directories for writing temporary and final results
    sitedir = os.path.join(maindir, sitename)
    tempdir = os.path.join(sitedir, 'proc_in')
    outdir = os.path.join(sitedir, 'proc_out')
    #######################################################################################
    # load the test site geometry into a vector object
    sites = vector.Vector('/path/to/your/testsites.shp')

    # query the test site by name; a column name 'Site_Name' must be saved in your shapefile
    site = sites['Site_Name={}'.format(lookup[sitename])]
    #######################################################################################
    # query the database for scenes to be processed
    with Archive(dbfile) as archive:
        selection_proc = archive.select(vectorobject=site,
                                        processdir=outdir,
                                        maxdate=maxdate,
                                        sensor=('S1A', 'S1B'),
                                        product='GRD',
                                        acquisition_mode='IW',
                                        vv=1)

    print('{0}: {1} scenes found for site {2}'.format(socket.gethostname(), len(selection_proc), sitename))
    #######################################################################################
    # call to processing utility
    if len(selection_proc) > 1:
        print('start processing')

        for scene in selection_proc:
            geocode(infile=scene, outdir=outdir, tr=resolution, scaling='db')
    return len(selection_proc)


if __name__ == '__main__':
    #######################################################################################
    # update SAR scene archive database

    archive_s1 = '/geonfs01_vol3/swos/data/sentinel1/GRD'
    scenes_s1 = finder(archive_s1, ['^S1[AB]'], regex=True, recursive=False)

    archive_ers_asar = '/geonfs01_vol1/ve39vem/swos_archive'
    scenes_ers_asar = finder(archive_ers_asar, ['*zip'])

    with Archive(dbfile) as archive:
        archive.insert(scenes_s1 + scenes_ers_asar)
    #######################################################################################
    # start the processing
    results = list(futures.map(worker, sites))
