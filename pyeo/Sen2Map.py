# -*- coding: utf-8 -*-
"""
Created on Sat Mar 24 12:11:00 2018

@author: Heiko Balzter
"""

#############################################################################
# read all Sentinel-2 band geotiffs in a directory and a shape file
#   and make RGB quicklook maps at different scales
# written for Python 3.6.4
#############################################################################

# TODO for John IMPORTANT:
# When you start the IPython Kernel, type in:
#   %matplotlib
# This will launch a graphical user interface (GUI) loop

########################
# TODO write a draw_north_arrow function that adds an artist to axis 2
# TODO separate geotiff conversion and 10 m resampling into 2 functions
# TODO plot multiple adjacent scenes onto the same map by providing a list of scene IDs to map_it instead of rgbdata and running readsen2rgb from within map_it
# TODO tiffdir: save outputs to a different subdirectory outside raw scene directory structure
########################

from cartopy.io.shapereader import Reader
from cartopy.feature import ShapelyFeature, BORDERS
import cartopy
import cartopy.crs as ccrs
#from cartopy.io.img_tiles import OSM
#import cartopy.feature as cfeature
#from cartopy.io import shapereader
#from cartopy.io.img_tiles import StamenTerrain
#from cartopy.io.img_tiles import GoogleTiles
#from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
import matplotlib.pyplot as plt
import matplotlib.patches as patches
#from matplotlib.path import Path
#import matplotlib.patheffects as PathEffects
#from matplotlib import patheffects
#import matplotlib.patches as mpatches
#import matplotlib.lines as mlines
import numpy as np
import os, sys
from os import listdir
from os.path import isfile, isdir, join
from osgeo import gdal, gdalnumeric, ogr, osr
from skimage import io
#import subprocess
gdal.UseExceptions()
io.use_plugin('matplotlib')
import pandas as pd
import subprocess
#import datetime
#import platform
#import datetime
#import math
import matplotlib.pyplot as plt
#from owslib.wmts import WebMapTileService


# The pyplot interface provides 4 commands that are useful for interactive control.
# plt.isinteractive() returns the interactive setting True|False
# plt.ion() turns interactive mode on
# plt.ioff() turns interactive mode off
# plt.draw() forces a figure redraw

#############################################################################
# OPTIONS
#############################################################################
# wd = '/scratch/clcr/shared/py/' # working directory on Linux HPC
wd = '/home/heiko/linuxpy/mexico/'  # working directory on Linux Virtual Box
datadir = wd + 'data/'  # directory of Sentinel L1C data files in .SAFE format
shapefile = 'Sitios_Poly.shp' # the shapefile resides in wd
bands = [5, 4, 3]  # band selection for RGB


#############################################################################
# FUNCTION DECLARATIONS
#############################################################################

def blank_axes(ax):
    """
    blank_axes:  blank the extraneous spines and tick marks for an axes

    Input:
    ax:  a matplotlib Axes object

    Output: None
    """

    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.yaxis.set_ticks_position('none')
    ax.xaxis.set_ticks_position('none')
    ax.tick_params(labelbottom='off', labeltop='off', labelleft='off', labelright='off', \
                   bottom='off', top='off', left='off', right='off')

# define functions to read/write floating point numbers from/to a text file
def read_floats(filename):
    with open(filename) as f:
        return [float(x) for x in f]
    f.close()

def write_floats(data, filename):
    file = open(filename, 'w')
    for item in data:
        file.write("%f\n" % item)
    file.close()

def get_gridlines(x0, x1, y0, y1, nticks):
    '''
    make neat gridline labels for map projections
        x0, x1 = minimum and maximum x positions in map projection coordinates
        y0, y1 = minimum and maximum y positions in map projection coordinates
        nticks = number of ticks / gridlines in x direction
        returns two numpy arrays with x and y tick positions
    '''
    # make sure gridline positions have min 2 digits
    ndigits = len(str(abs(x0)).split('.')[0])  # number of digits before the decimal point
    xx0 = x0
    xfactor = 1  # how many time do we need to multiply by 10
    while ndigits < 2:
        xx0 = xx0 * 10
        xfactor = xfactor * 10
        ndigits = len(str(abs(xx0)).split('.')[0])  # number of digits before the decimal point
        if xfactor > 100000:
            print('\nError in XFactor while loop!')
            break
    x0 = round(x0 * xfactor, 0) / xfactor
    x1 = round(x1 * xfactor, 0) / xfactor
    y0 = round(y0 * xfactor, 0) / xfactor
    y1 = round(y1 * xfactor, 0) / xfactor
    # make sure gridline positions have max 3 digits
    ndigits = len(str(abs(x0)).split('.')[0])  # number of digits before the decimal point
    xx0 = x0
    xfactor = 1  # how many time do we need to divide by 10
    while ndigits > 3:
        xx0 = xx0 / 10
        xfactor = xfactor * 10
        ndigits = len(str(abs(xx0)).split('.')[0])  # number of digits before the decimal point
        if xfactor > 100000:
            print('\nError in XFactor while loop!')
            break
    x0 = round(x0 / xfactor, 0) * xfactor
    x1 = round(x1 / xfactor, 0) * xfactor
    y0 = round(y0 / xfactor, 0) * xfactor
    y1 = round(y1 / xfactor, 0) * xfactor
    # carry on
    dx = (x1 - x0) / nticks
    dy = (y1 - y0) / nticks
    xticks = np.arange(x0, x1 + dx, dx)
    yticks = np.arange(y0, y1 + dy, dy)
    return xticks, yticks


# plot a scale bar with 4 subdivisions on the left side of the map
def scale_bar_left(ax, bars=4, length=None, location=(0.1, 0.05), linewidth=3, col='black'):
    """
    USE DRAW_SCALE_BAR instead

    ax is the axes to draw the scalebar on.
    bars is the number of subdivisions of the bar (black and white chunks)
    length is the length of the scalebar in km.
    location is left side of the scalebar in axis coordinates.
    (ie. 0 is the left side of the plot)
    linewidth is the thickness of the scalebar.
    color is the color of the scale bar and the text

    modified from
    https://stackoverflow.com/questions/32333870/how-can-i-show-a-km-ruler-on-a-cartopy-matplotlib-plot/35705477#35705477

    """
    # Get the limits of the axis in lat long
    llx0, llx1, lly0, lly1 = ax.get_extent(ccrs.PlateCarree())
    # Make tmc aligned to the left of the map,
    # vertically at scale bar location
    sbllx = llx0 + (llx1 - llx0) * location[0]
    sblly = lly0 + (lly1 - lly0) * location[1]
    tmc = ccrs.TransverseMercator(sbllx, sblly)
    # Get the extent of the plotted area in coordinates in metres
    x0, x1, y0, y1 = ax.get_extent(tmc)
    # Turn the specified scalebar location into coordinates in metres
    sbx = x0 + (x1 - x0) * location[0]
    sby = y0 + (y1 - y0) * location[1]

    # Calculate a scale bar length if none has been given
    # (Theres probably a more pythonic way of rounding the number but this works)
    if not length:
        length = (x1 - x0) / 5000  # in km
        ndim = int(np.floor(np.log10(length)))  # number of digits in number
        length = round(length, -ndim)  # round to 1sf

        # Returns numbers starting with the list
        def scale_number(x):
            if str(x)[0] in ['1', '2', '5']:
                return int(x)
            else:
                return scale_number(x - 10 ** ndim)

        length = scale_number(length)

    # Generate the x coordinate for the ends of the scalebar
    bar_xs = [sbx, sbx + length * 1000 / bars]
    # Plot the scalebar chunks
    barcol = 'white'
    for i in range(0, bars):
        # plot the chunk
        ax.plot(bar_xs, [sby, sby], transform=tmc, color=barcol, linewidth=linewidth)
        # alternate the colour
        if barcol == 'white':
            barcol = col
        else:
            barcol = 'white'
        # Generate the x coordinate for the number
        bar_xt = sbx + i * length * 1000 / bars
        # Plot the scalebar label for that chunk
        ax.text(bar_xt, sby, str(round(i * length / bars)), transform=tmc,
                horizontalalignment='center', verticalalignment='bottom',
                color=col)
        # work out the position of the next chunk of the bar
        bar_xs[0] = bar_xs[1]
        bar_xs[1] = bar_xs[1] + length * 1000 / bars
    # Generate the x coordinate for the last number
    bar_xt = sbx + length * 1000
    # Plot the last scalebar label
    ax.text(bar_xt, sby, str(round(length)), transform=tmc,
            horizontalalignment='center', verticalalignment='bottom',
            color=col)
    # Plot the unit label below the bar
    bar_xt = sbx + length * 1000 / 2
    bar_yt = y0 + (y1 - y0) * (location[1] / 4)
    ax.text(bar_xt, bar_yt, 'km', transform=tmc, horizontalalignment='center',
            verticalalignment='bottom', color=col)


# function to convert coordinates
def convertXY(xy_source, inproj, outproj):
    shape = xy_source[0, :, :].shape
    size = xy_source[0, :, :].size
    # the ct object takes and returns pairs of x,y, not 2d grids
    # so the the grid needs to be reshaped (flattened) and back.
    ct = osr.CoordinateTransformation(inproj, outproj)
    xy_target = np.array(ct.TransformPoints(xy_source.reshape(2, size).T))
    xx = xy_target[:, 0].reshape(shape)
    yy = xy_target[:, 1].reshape(shape)
    return xx, yy


# This function will convert the rasterized clipper shapefile to a mask for use within GDAL.
def imageToArray(i):
    """
    Converts a Python Imaging Library array to a
    gdalnumeric image.
    """
    a = gdalnumeric.fromstring(i.tostring(), 'b')
    a.shape = i.im.size[1], i.im.size[0]
    return a


def world2Pixel(geoMatrix, x, y):
    """
    Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
    the pixel location of a geospatial coordinate
    """
    ulX = geoMatrix[0]
    ulY = geoMatrix[3]
    xDist = geoMatrix[1]
    yDist = geoMatrix[5]
    rtnX = geoMatrix[2]
    rtnY = geoMatrix[4]
    pixel = int((x - ulX) / xDist)
    line = int((ulY - y) / xDist)
    return (pixel, line)


def transformxy(s_srs, t_srs, xcoord, ycoord):
    """
    Transforms a point coordinate x,y from a source reference system (s_srs)
    to a target reference system (t_srs)
    """
    geom = ogr.Geometry(ogr.wkbPoint)
    geom.SetPoint_2D(0, xcoord, ycoord)
    geom.AssignSpatialReference(s_srs)
    geom.TransformTo(t_srs)
    return geom.GetPoint_2D()


def projectshape(inshp, outshp, t_srs):
    """
    Reprojects an ESRI shapefile from its source reference system
    to a target reference system (e.g. t_srs = 4326)
    filenames must include the full directory paths
    requires:
        from osgeo import ogr, osr
        import os
    """

    driver = ogr.GetDriverByName('ESRI Shapefile')  # get shapefile driver
    infile = driver.Open(inshp, 0)
    if infile is None:
        print('Could not open ' + inshp)
        sys.exit(1)  # exit with an error code
    inLayer = infile.GetLayer()  # get input layer
    inSpatialRef = inLayer.GetSpatialRef()  # get source spatial reference system
    # or input SpatialReference manually here
    #   inSpatialRef = osr.SpatialReference()
    #   inSpatialRef.ImportFromEPSG(2927)
    outSpatialRef = osr.SpatialReference()
    outSpatialRef.ImportFromEPSG(t_srs)
    # create the CoordinateTransformation
    coordTrans = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
    # create the output layer
    if os.path.exists(outshp):
        driver.DeleteDataSource(outshp)
    outDataSet = driver.CreateDataSource(outshp)
    outLayer = outDataSet.CreateLayer("basemap_" + str(t_srs), geom_type=ogr.wkbMultiPolygon)
    # add fields
    inLayerDefn = inLayer.GetLayerDefn()
    for i in range(0, inLayerDefn.GetFieldCount()):
        fieldDefn = inLayerDefn.GetFieldDefn(i)
        outLayer.CreateField(fieldDefn)
    # get the output layer's feature definition
    outLayerDefn = outLayer.GetLayerDefn()
    # loop through the input features
    inFeature = inLayer.GetNextFeature()
    while inFeature:
        # get the input geometry
        geom = inFeature.GetGeometryRef()
        # reproject the geometry
        geom.Transform(coordTrans)
        # create a new feature
        outFeature = ogr.Feature(outLayerDefn)
        # set the geometry and attribute
        outFeature.SetGeometry(geom)
        for i in range(0, outLayerDefn.GetFieldCount()):
            outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(), inFeature.GetField(i))
        # add the feature to the shapefile
        outLayer.CreateFeature(outFeature)
        # dereference the features and get the next input feature
        outFeature = None
        inFeature = inLayer.GetNextFeature()
    # Save and close the shapefiles
    inDataSet = None
    outDataSet = None
    # Try to open the output file to check it worked
    outfile = driver.Open(outshp, 0)
    if outfile is None:
        print('Failed to create ' + outshp)
        sys.exit(1)  # exit with an error code
    else:
        print('Reprojection of shapefile seems to have worked.')
    return None


def OpenArray(array, prototype_ds=None, xoff=0, yoff=0):
    #  this is basically an overloaded version of the gdal_array.OpenArray passing in xoff, yoff explicitly
    #  so we can pass these params off to CopyDatasetInfo
    ds = gdal.Open(gdalnumeric.GetArrayFilename(array))

    if ds is not None and prototype_ds is not None:
        if type(prototype_ds).__name__ == 'str':
            prototype_ds = gdal.Open(prototype_ds)
        if prototype_ds is not None:
            gdalnumeric.CopyDatasetInfo(prototype_ds, ds, xoff=xoff, yoff=yoff)
    return ds


def histogram(a, bins=range(0, 256)):
    """
    Histogram function for multi-dimensional array.
    a = array
    bins = range of numbers to match
    """
    fa = a.flat
    n = gdalnumeric.searchsorted(gdalnumeric.sort(fa), bins)
    n = gdalnumeric.concatenate([n, [len(fa)]])
    hist = n[1:] - n[:-1]
    return hist


def stretch(im, nbins=256, nozero=True):
    """
    Performs a histogram stretch on an ndarray image.
    """
    # modified from http://www.janeriksolem.net/2009/06/histogram-equalization-with-python-and.html

    # ignore zeroes
    if nozero:
        im2 = im[np.not_equal(im, 0)]
    else:
        im2 = im
    # get image histogram
    image_histogram, bins = np.histogram(im2.flatten(), nbins, normed=True)
    cdf = image_histogram.cumsum()  # cumulative distribution function
    cdf = 255 * cdf / cdf[-1]  # normalize
    # use linear interpolation of cdf to find new pixel values
    image_equalized = np.interp(im.flatten(), bins[:-1], cdf)
    return image_equalized.reshape(im.shape), cdf


def read_sen2_rgb(rgbfiles, enhance=True):
    '''
    reads in 3 separate geotiff files as R G and B channels
    rgbfiles: list of three filenames including directory structure
    enhance = True: applies histogram stretching (optional)
    returns a data frame scaled to unsigned 8 bit integer values
    '''
    # make array of 8-bit unsigned integers to be memory efficient
    # open the first file with GDAL to get dimensions
    ds = gdal.Open(rgbfiles[0])
    data = ds.ReadAsArray()
    rgbdata = np.zeros([len(bands), data.shape[0], data.shape[1]], \
                       dtype=np.uint8)

    for i, thisfile in enumerate(rgbfiles):
        print('Reading data from ' + thisfile)

        # open the file with GDAL
        ds = gdal.Open(thisfile)
        data = ds.ReadAsArray()

        # only process single-band files, these have not got 3 bands
        if data.shape[0] > 3:
            # histogram stretching and keeping the values in
            #   the RGB data array as 8 bit unsigned integers
            rgbdata[i, :, :] = np.uint8(stretch(data)[0])

        ds = None
    return rgbdata


def map_it_old(rgbdata, tifproj, mapextent, shapefile, plotfile='map.jpg',
           plottitle='', figsizex=10, figsizey=10):
    '''
    standard map making function that saves a jpeg file of the output
    and visualises it on screen
    rgbdata = numpy array of the red, green and blue channels, made by read_sen2rgb
    tifproj = map projection of the tiff files from which the rgbdata originate
    mapextent = extent of the map in map coordinates
    shapefile = shapefile name to be plotted on top of the map
    shpproj = map projection of the shapefile
    plotfile = output filename for the map plot
    plottitle = text to be written above the map
    figsizex = width of the figure in inches
    figsizey = height of the figure in inches
    '''
    # get shapefile projection from the file
    # get driver to read a shapefile and open it
    driver = ogr.GetDriverByName('ESRI Shapefile')
    dataSource = driver.Open(shapefile, 0)
    if dataSource is None:
        print('Could not open ' + shapefile)
        sys.exit(1)  # exit with an error code
    # get the layer from the shapefile
    layer = dataSource.GetLayer()
    # get the projection information and convert to wkt
    projsr = layer.GetSpatialRef()
    projwkt = projsr.ExportToWkt()
    projosr = osr.SpatialReference()
    projosr.ImportFromWkt(projwkt)
    # convert wkt projection to Cartopy projection
    projcs = projosr.GetAuthorityCode('PROJCS')
    shapeproj = ccrs.epsg(projcs)

    # make the figure and the axes
    subplot_kw = dict(projection=tifproj)
    fig, ax = plt.subplots(figsize=(figsizex, figsizey),
                           subplot_kw=subplot_kw)

    # set a margin around the data
    ax.set_xmargin(0.05)
    ax.set_ymargin(0.10)

    # add a background image for rendering
    ax.stock_img()

    # show the data from the geotiff RGB image
    img = ax.imshow(rgbdata[:3, :, :].transpose((1, 2, 0)),
                    extent=extent, origin='upper')

    # read shapefile and plot it onto the tiff image map
    shape_feature = ShapelyFeature(Reader(shapefile).geometries(),
                                   crs=shapeproj, edgecolor='yellow',
                                   facecolor='none')
    ax.add_feature(shape_feature)

    # add a title
    plt.title(plottitle)

    # set map extent
    ax.set_extent(mapextent, tifproj)

    # add coastlines
    ax.coastlines(resolution='10m', color='navy', linewidth=1)

    # add lakes and rivers
    ax.add_feature(cartopy.feature.LAKES, alpha=0.5)
    ax.add_feature(cartopy.feature.RIVERS)

    # add borders
    BORDERS.scale = '10m'
    ax.add_feature(BORDERS, color='red')

    # format the gridline positions nicely
    xticks, yticks = get_gridlines(mapextent[0], mapextent[1],
                                   mapextent[2], mapextent[3],
                                   nticks=10)

    # add gridlines
    gl = ax.gridlines(crs=tifproj, xlocs=xticks, ylocs=yticks,
                      linestyle='--', color='grey', alpha=1, linewidth=1)

    # add ticks
    ax.set_xticks(xticks, crs=tifproj)
    ax.set_yticks(yticks, crs=tifproj)

    # stagger x gridline / tick labels
    labels = ax.set_xticklabels(xticks)
    for i, label in enumerate(labels):
        label.set_y(label.get_position()[1] - (i % 2) * 0.075)

    # add scale bar
    scale_bar_left(ax, bars=4, length=40, col='dimgrey')

    # show the map
    plt.show()

    # save it to a file
    fig.savefig(plotfile)


def draw_scale_bar(ax, tifproj, bars=4, length=None, location=(0.1, 0.8), linewidth=5, col='black', zorder=20):
    """
    Plot a nice scale bar with 4 subdivisions on an axis linked to the map scale.

    ax is the axes to draw the scalebar on.
    tifproj is the map projection
    bars is the number of subdivisions of the bar (black and white chunks)
    length is the length of the scalebar in km.
    location is left side of the scalebar in axis coordinates.
    (ie. 0 is the left side of the plot)
    linewidth is the thickness of the scalebar.
    color is the color of the scale bar and the text

    modified from
    https://stackoverflow.com/questions/32333870/how-can-i-show-a-km-ruler-on-a-cartopy-matplotlib-plot/35705477#35705477

    """
    # Get the limits of the axis in map coordinates
    x0, x1, y0, y1 = ax.get_extent(tifproj)

    # Set the relative position of the scale bar
    sbllx = x0 + (x1 - x0) * location[0]
    sblly = y0 + (y1 - y0) * location[1]

    # Turn the specified relative scalebar location into coordinates in metres
    sbx = x0 + (x1 - x0) * location[0]
    sby = y0 + (y1 - y0) * location[1]

    # Get the thickness of the scalebar
    thickness = (y1 - y0) / 20

    # Calculate a scale bar length if none has been given
    if not length:
        length = (x1 - x0) / 1000 / bars  # in km
        ndim = int(np.floor(np.log10(length)))  # number of digits in number
        length = round(length, -ndim)  # round to 1sf

        # Returns numbers starting with the list
        def scale_number(x):
            if str(x)[0] in ['1', '2', '5']:
                return int(x)
            else:
                return scale_number(x - 10 ** ndim)

        length = scale_number(length)

    # Generate the x coordinate for the ends of the scalebar
    bar_xs = [sbx, sbx + length * 1000 / bars]

    # Generate the y coordinate for the ends of the scalebar
    bar_ys = [sby, sby + thickness]

    # Plot the scalebar chunks
    barcol = 'white'
    for i in range(0, bars):
        # plot the chunk
        rect = patches.Rectangle((bar_xs[0], bar_ys[0]), bar_xs[1] - bar_xs[0], bar_ys[1] - bar_ys[0],
                                 linewidth=1, edgecolor='black', facecolor=barcol)
        ax.add_patch(rect)

        #        ax.plot(bar_xs, bar_ys, transform=tifproj, color=barcol, linewidth=linewidth, zorder=zorder)

        # alternate the colour
        if barcol == 'white':
            barcol = col
        else:
            barcol = 'white'
        # Generate the x,y coordinates for the number
        bar_xt = sbx + i * length * 1000 / bars
        bar_yt = sby + thickness

        # Plot the scalebar label for that chunk
        ax.text(bar_xt, bar_yt, str(round(i * length / bars)), transform=tifproj,
                horizontalalignment='center', verticalalignment='bottom',
                color=col, zorder=zorder)
        # work out the position of the next chunk of the bar
        bar_xs[0] = bar_xs[1]
        bar_xs[1] = bar_xs[1] + length * 1000 / bars
    # Generate the x coordinate for the last number
    bar_xt = sbx + length * 1000
    # Plot the last scalebar label
    t = ax.text(bar_xt, bar_yt, str(round(length)) + ' km', transform=tifproj,
                horizontalalignment='center', verticalalignment='bottom',
                color=col, zorder=zorder)


def test_map_it2(rgbdata, tifproj, mapextent, shapefile, plotfile='map.jpg',
                 plottitle='', figsizex=10, figsizey=10):
    '''
    This version attempt to expand the map towards the bottom and plot the scale bar there.
    It is not satisfactory that the background image covers that area and a box is drawn around it.

    standard map making function that saves a jpeg file of the output
    and visualises it on screen
    rgbdata = numpy array of the red, green and blue channels, made by read_sen2rgb
    tifproj = map projection of the tiff files from which the rgbdata originate
    mapextent = extent of the map in map coordinates
    shapefile = shapefile name to be plotted on top of the map
    shpproj = map projection of the shapefile
    plotfile = output filename for the map plot
    plottitle = text to be written above the map
    figsizex = width of the figure in inches
    figsizey = height of the figure in inches
    '''
    # get shapefile projection from the file
    # get driver to read a shapefile and open it
    driver = ogr.GetDriverByName('ESRI Shapefile')
    dataSource = driver.Open(shapefile, 0)
    if dataSource is None:
        print('Could not open ' + shapefile)
        sys.exit(1)  # exit with an error code
    # get the layer from the shapefile
    layer = dataSource.GetLayer()
    # get the projection information and convert to wkt
    projsr = layer.GetSpatialRef()
    projwkt = projsr.ExportToWkt()
    projosr = osr.SpatialReference()
    projosr.ImportFromWkt(projwkt)
    # convert wkt projection to Cartopy projection
    projcs = projosr.GetAuthorityCode('PROJCS')
    shapeproj = ccrs.epsg(projcs)

    # make the figure and the axes
    subplot_kw = dict(projection=tifproj)
    fig, ax = plt.subplots(figsize=(figsizex, figsizey),
                           subplot_kw=subplot_kw)

    # set a margin around the data
    ax.set_xmargin(0.05)
    ax.set_ymargin(0.10)

    # add a background image for rendering
    ax.stock_img()

    # show the data from the geotiff RGB image
    img = ax.imshow(rgbdata[:3, :, :].transpose((1, 2, 0)),
                    extent=extent, origin='upper')

    # read shapefile and plot it onto the tiff image map
    shape_feature = ShapelyFeature(Reader(shapefile).geometries(),
                                   crs=shapeproj, edgecolor='yellow',
                                   facecolor='none')
    ax.add_feature(shape_feature)

    # add a title
    plt.title(plottitle)

    # set map extent plus a margin for the scale bar
    h = mapextent[3] - mapextent[2]  # height of the image on the map
    w = mapextent[1] - mapextent[0]  # width of the image on the map
    areaextent = (mapextent[0], mapextent[1], mapextent[2] - h / 10, mapextent[3])
    ax.set_extent(areaextent, tifproj)

    # draw the x axis where the image ends and the scale bar area of the map begins
    ax.spines['left'].set_position(('data', mapextent[0]))
    ax.spines['right'].set_color('none')
    ax.spines['bottom'].set_position(('data', mapextent[2]))
    ax.spines['top'].set_color('none')
    ax.spines['left'].set_smart_bounds(True)
    ax.spines['bottom'].set_smart_bounds(True)

    # do not draw the bounding box
    plt.box(on=None)

    # make bottom axis line invisible
    #    ax.spines["top"].set_visible(True)
    #    ax.spines["right"].set_visible(True)
    #    ax.spines["bottom"].set_visible(False)
    #    ax.spines["left"].set_visible(True)

    # add coastlines
    ax.coastlines(resolution='10m', color='navy', linewidth=1)

    # add lakes and rivers
    ax.add_feature(cartopy.feature.LAKES, alpha=0.5)
    ax.add_feature(cartopy.feature.RIVERS)

    # add borders
    BORDERS.scale = '10m'
    ax.add_feature(BORDERS, color='red')

    # format the gridline positions nicely
    xticks, yticks = get_gridlines(mapextent[0], mapextent[1],
                                   mapextent[2], mapextent[3],
                                   nticks=10)

    # add gridlines
    gl = ax.gridlines(crs=tifproj, xlocs=xticks, ylocs=yticks,
                      linestyle='--', color='grey', alpha=1, linewidth=1)

    # add ticks
    ax.set_xticks(xticks, crs=tifproj)
    ax.set_yticks(yticks, crs=tifproj)

    # stagger x gridline / tick labels
    labels = ax.set_xticklabels(xticks)
    for i, label in enumerate(labels):
        label.set_y(label.get_position()[1] - (i % 2) * 0.2)

    # add scale bar
    draw_scale_bar(ax, bars=4, length=40, location=(0.1, 0.025), tifproj=projection, col='black')

    # show the map
    plt.show()

    # save it to a file
    fig.savefig(plotfile)


def map_it(rgbdata, tifproj, mapextent, shapefile, plotfile='map.jpg',
            plottitle='', figsizex=8, figsizey=10):
    '''
    New map_it function with improved scale bar plotting below the map.
    This version creates two subplots, one for the map and one for the annotation.

    rgbdata = numpy array of the red, green and blue channels, made by read_sen2rgb
    tifproj = map projection of the tiff files from which the rgbdata originate
    mapextent = extent of the map in map coordinates
    shapefile = shapefile name to be plotted on top of the map
    shpproj = map projection of the shapefile
    plotfile = output filename for the map plot
    plottitle = text to be written above the map
    figsizex = width of the figure in inches
    figsizey = height of the figure in inches
    '''

    # get shapefile projection from the file
    # get driver to read a shapefile and open it
    driver = ogr.GetDriverByName('ESRI Shapefile')
    dataSource = driver.Open(shapefile, 0)
    if dataSource is None:
        print('Could not open ' + shapefile)
        sys.exit(1)  # exit with an error code
    # get the layer from the shapefile
    layer = dataSource.GetLayer()
    # get the projection information and convert to wkt
    projsr = layer.GetSpatialRef()
    projwkt = projsr.ExportToWkt()
    projosr = osr.SpatialReference()
    projosr.ImportFromWkt(projwkt)
    # convert wkt projection to Cartopy projection
    projcs = projosr.GetAuthorityCode('PROJCS')
    shapeproj = ccrs.epsg(projcs)

    # definitions for the axes in map coordinates
    margin = 0.2  # set aside this proportion of the height of the figure for the annotations
    left0, right0 = mapextent[0], mapextent[1]
    bottom0, top0 = mapextent[2] - (mapextent[3] - mapextent[2]) * margin, mapextent[3]
    left1, right1 = mapextent[0], mapextent[1]
    bottom1, top1 = mapextent[2], mapextent[3]
    left2, right2 = mapextent[0], mapextent[1]
    bottom2, top2 = mapextent[2] - (mapextent[3] - mapextent[2]) * margin, mapextent[2]

    # set bounding boxes for the two drawing areas
    #   extent0 covers (mapextent plus the margin below it)
    #   extent1 covers the area for the map (the same as mapextent)
    #   extent2 covers the area below the map for scalebar annotation (a margin outside of mapextent)
    extent0 = (left0, right0, bottom0, top0)
    extent1 = (left1, right1, bottom1, top1)
    extent2 = (left2, right2, bottom2, top2)
    rect0 = [left0, right0 - left0, bottom0, top0 - bottom0]
    rect1 = [left1, right1 - left1, bottom1, top1 - bottom1]
    rect2 = [left2, right2 - left2, bottom2, top2 - bottom2]

    # make the figure and the axes
    subplot_kw = dict(projection=tifproj)
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(figsizex, figsizey),
                                   gridspec_kw={'height_ratios': [8, 2]},
                                   subplot_kw=subplot_kw)

    # set a margin around the data
    ax1.set_xmargin(0.05)
    ax1.set_ymargin(0.10)

    # set map extent
    ax1.set_extent(extent1, tifproj)

    # set matching extent of the annotation area for the scale bar
    ax2.set_extent(extent2, tifproj)

    # add a background image for rendering
    ax1.stock_img()

    # show the data from the geotiff RGB image
    img = ax1.imshow(rgbdata[:3, :, :].transpose((1, 2, 0)),
                     extent=extent, origin='upper', zorder=1)

    #  read shapefile and plot it onto the tiff image map
    shape_feature = ShapelyFeature(Reader(shapefile).geometries(), crs=shapeproj,
                                   edgecolor='yellow', linewidth=2,
                                   facecolor='none')
    # higher zorder means that the shapefile is plotted over the image
    ax1.add_feature(shape_feature, zorder=1.1)

    # add a title
    ax1.set_title(plottitle)

    # add coastlines
    ax1.coastlines(resolution='10m', color='navy', linewidth=1)

    # add lakes and rivers
    ax1.add_feature(cartopy.feature.LAKES, alpha=0.5)
    ax1.add_feature(cartopy.feature.RIVERS)

    # add borders
    BORDERS.scale = '10m'
    ax1.add_feature(BORDERS, color='red')

    # draw the x axis where the image ends and the scale bar area of the map begins
    ax1.spines['left'].set_position(('data', extent1[0]))
    ax1.spines['right'].set_color('none')
    ax1.spines['bottom'].set_position(('data', extent1[2]))
    ax1.spines['top'].set_color('none')
    ax1.spines['left'].set_smart_bounds(True)
    ax1.spines['bottom'].set_smart_bounds(True)

    ax2.spines['left'].set_position(('data', extent2[0]))
    ax2.spines['bottom'].set_position(('data', extent2[2]))
    ax2.spines['left'].set_smart_bounds(True)
    ax2.spines['bottom'].set_smart_bounds(True)

    # do not draw the bounding box around the scale bar area. This seems to be the only way to make this work.
    #   there is a bug in Cartopy that always draws the box.
    ax2.outline_patch.set_visible(False)

    # draw a white box over the bottom part of the figure area as a space for the scale bar etc.
    # ax2.axhspan(ymin=extent2[2], ymax=extent2[3], fill=True, facecolor="white", zorder=1.2)

    # format the gridline positions nicely
    xticks, yticks = get_gridlines(extent1[0], extent1[1], extent1[2], extent1[3], nticks=10)

    # add gridlines
    gl = ax1.gridlines(crs=tifproj, xlocs=xticks, ylocs=yticks, linestyle='--', color='grey',
                       alpha=1, linewidth=1, zorder=1.3)

    # add ticks
    ax1.set_xticks(xticks, crs=tifproj)
    ax1.set_yticks(yticks, crs=tifproj)

    # stagger x gridline / tick labels
    labels = ax1.set_xticklabels(xticks)
    for i, label in enumerate(labels):
        label.set_y(label.get_position()[1] - (i % 2) * 0.1)

    # rotate the font orientation of the axis tick labels
    plt.setp(ax1.get_xticklabels(), rotation=30, horizontalalignment='right')

    # set axis tick mark parameters
    ax1.tick_params(zorder=1.4)  # bring to foreground
    # N.B. note that zorder of axis ticks is reset to he default of 2.5 when the plot is drawn. This is a known bug.

    # add scale bar on the second axes in row 2 of the subplots
    draw_scale_bar(ax2, bars=4, length=40, col='black', tifproj=projection, zorder=4)

    # show the map
    fig.tight_layout()
    fig.show()

    # save it to a file
    # plotfile = plotdir + allscenes[x].split('.')[0] + '_map1.jpg'
    fig.savefig(plotfile)
    plt.close(fig)


#############################################################################
# MAIN
#############################################################################

# go to working directory
os.chdir(wd)

###################################################
# make a 'plots' directory (if it does not exist yet) for map output files
###################################################
plotdir = wd + 'plots_' + shapefile.split(".")[0] + "/"
if not os.path.exists(plotdir):
    print("Creating directory: ", plotdir)
    os.mkdir(plotdir)

###################################################
# get names of all scenes
###################################################

# get list of all data subdirectories (one for each image)
allscenes = [f for f in listdir(datadir) if isdir(join(datadir, f))]
print('\nList of Sentinel-2 scenes:')
for scene in allscenes:
    print(scene)
print('\n')

###################################################
# resample all Sentinel-2 scenes in the data directory to 10 m
###################################################
tiffdirs = [''] # make a list of all tiff file directories of the same length as the number of scenes
for x in range(len(allscenes)):
    if allscenes[x].split(".")[1] == "SAFE":
        # open the file
        print('\n******************************')
        print("Reading scene", x + 1, ":", allscenes[x])
        print('******************************\n')

        # set working directory to the Sentinel scene subdirectory
        scenedir = datadir + allscenes[x] + "/"
        os.chdir(scenedir)

        ###################################################
        # get footprint of the scene from the metadatafile
        ###################################################
        # get the list of filenames ending in .xml, but exclude 'INSPIRE.xml'
        xmlfiles = [f for f in os.listdir(scenedir) if f.endswith('.xml') & (1 - f.startswith('INSPIRE'))]
        #print('Reading footprint from ' + xmlfiles[0])
        # use the first .xml file in the directory
        with open(xmlfiles[0]) as f:
            content = f.readlines()
        # remove whitespace characters like `\n` at the end of each line
        content = [x.strip() for x in content]
        # find the footprint in the metadata
        footprint = [x for x in content if x.startswith('<EXT_POS_LIST>')]
        # the first element of the returned list is a string
        #   so extract the string and split it
        footprint = footprint[0].split(" ")
        #   and split off the metadata text
        footprint[0] = footprint[0].split(">")[1]
        #   and remove the metadata text at the end of the list
        footprint = footprint[:-1]
        # convert the string list to floats
        footprint = [float(s) for s in footprint]
        # list slicing to separate lon and lat coordinates: list[start:stop:step]
        footprinty = footprint[0::2]  # latitudes
        footprintx = footprint[1::2]  # longitudes
        #print(footprint)

        # set working directory to the Granule subdirectory
        os.chdir(datadir + allscenes[x] + "/" + "GRANULE" + "/")
        sdir = listdir()[0]  # only one subdirectory expected in this directory

        # set working directory to the image data subdirectory
        imgdir = datadir + allscenes[x] + "/" + "GRANULE" + "/" + sdir + "/" + "IMG_DATA" + "/"
        os.chdir(imgdir)

        ###################################################
        # get the list of filenames for all bands in .jp2 format
        ###################################################
        sbands = sorted([f for f in os.listdir(imgdir) if f.endswith('.jp2')])
        print('Bands:')
        for band in sbands:
            print(band)
        nbands = len(sbands)  # get the number of bands in the image
        print('\n')

        ###################################################
        # load all bands to get row and column numbers, and resample to 10 m
        ###################################################
        ncolmax = nrowmax = 0
        obands = sbands  # filenames of output tiff files, all at 10 m resolution

        # in the scene directory, make a 'tiff' subdirectory for 10 m Geotiffs
        tiffdir = scenedir + 'tiff/'
        if not os.path.exists(tiffdir):
            print("Creating directory: ", tiffdir)
            os.mkdir(tiffdir)
        if x == 1:
            tiffdirs[0] = tiffdir
        else:
            tiffdirs.append(tiffdir) # remember all tiff file directories later

        ###################################################
        # process all the bands to 10 m resolution
        ###################################################

        # enumerate produces a counter and the contents of the band list
        for i, iband in enumerate(sbands):

            # open a band
            bandx = gdal.Open(iband, gdal.GA_Update)

            # get image dimensions
            ncols = bandx.RasterXSize
            nrows = bandx.RasterYSize

            # get raster georeferencing information
            geotrans = bandx.GetGeoTransform()
            ulx = geotrans[0]  # Upper Left corner coordinate in x
            uly = geotrans[3]  # Upper Left corner coordinate in y
            pixelWidth = geotrans[1]  # pixel spacing in map units in x
            pixelHeight = geotrans[5]  # (negative) pixel spacing in y
            print("Band %s has %6d columns, %6d rows and a %d m resolution." \
                  % (iband, ncols, nrows, pixelWidth))
            # scale factor for resampling to 10 m pixel resolution
            sf = abs(int(pixelWidth / 10))
            # determining the maximum number of columns and rows at 10 m
            ncolmax = max(ncols * sf, ncolmax)
            nrowmax = max(nrows * sf, nrowmax)

            # resample the 20 m and 40 m images to 10 m and convert to Geotiff
            if pixelWidth != 999:  # can be removed, is redundant as all images will be converted to GeoTiff
                print('  Resampling %s image from %d m to 10 m resolution and converting to Geotiff' \
                      % (iband, pixelWidth))
                # define the zoom factor in %
                zf = str(pixelWidth * 10) + '%'
                # define an output file name
                obands[i] = iband[:-4] + '_10m.tif'
                # assemble command line code
                res_cmd = ['gdal_translate', '-outsize', zf, zf, '-of', 'GTiff',
                           iband, tiffdir + obands[i]]
            # save geotiff file at 10 m resolution
            subprocess.call(res_cmd)

            #close GDAL file
            bandx = None

        print("Output number of columns = %6d\nOutput number of rows = %6d." \
              % (ncolmax, nrowmax))

        print("\n")
        print("Resampling to 10 m resolution and conversion to Geotiff completed.")
        print("\n")

###################################################
# make maps from all Sentinel-2 Geotiffs
###################################################
for x in range(len(allscenes)):

        print('\n******************************')
        print("Reading scene", x + 1, ":", allscenes[x])
        print('******************************\n')

        ###################################################
        # Make RGB maps from three Geotiff files
        ###################################################

        print('Making maps from Geotiff RGB files')

        # get names of all 10 m resolution geotiff files
        tiffdir = tiffdirs[x]
        os.chdir(tiffdir)
        allfiles = sorted([f for f in os.listdir(tiffdir) if f.endswith('.tif')])
        nfiles = len(allfiles)
        print('\nProcessing %d Geotiff files:' % nfiles)
        for thisfile in allfiles:
            print(thisfile)
        print('\n\n')

        ###################################################
        # read and plot the selected RGB bands / geotiffs onto a map
        ###################################################

        # identify the filenames of the geotiff files for RGB map display
        rgbfiles = []
        for i in bands:
            rgbfiles.append(allfiles[i - 1])
        for thisfile in rgbfiles:
            print(thisfile)
        print('\n\n')

        # open the first tiff file with GDAL to get file dimensions
        thisfile = allfiles[0]
        ds = gdal.Open(thisfile)
        data = ds.ReadAsArray()

        # get the projection information and convert to wkt
        gt = ds.GetGeoTransform()
        proj = ds.GetProjection()
        inproj = osr.SpatialReference()
        inproj.ImportFromWkt(proj)

        # convert wkt projection to Cartopy projection
        projcs = inproj.GetAuthorityCode('PROJCS')
        projection = ccrs.epsg(projcs)

        # get the extent of the image
        extent = (gt[0], gt[0] + ds.RasterXSize * gt[1],
                  gt[3] + ds.RasterYSize * gt[5], gt[3])

        # read in the three geotiff files, one for each band
        rgbdata = read_sen2_rgb(rgbfiles)

        # close the GDAL file
        ds = None

        #######################################
        # Overview map: make a map plot of the tiff file in the image projection
        #######################################
        plotfile = allscenes[x].split('.')[0] + '_map1.jpg'
        title = allscenes[x].split('.')[0]
        mapextent = extent
        map_it(rgbdata, tifproj=projection, mapextent=mapextent, shapefile=wd + shapefile, plotfile=plotdir + plotfile,
                plottitle=title)

        #######################################
        # Zoom out
        #######################################
        plotfile = allscenes[x].split('.')[0] + '_map2.jpg'
        title = allscenes[x].split('.')[0]
        # zoom out (negative values zoom out, positive zoom in)
        zf = -2
        # offsets in map coordinates
        width = extent[1] - extent[0]
        height = extent[3] - extent[2]
        xoffset = 0
        yoffset = 0
        # need to unpack the tuple 'extent' and create a new tuple 'mapextent'
        mapextent = (extent[0] + width / zf / 2 + xoffset,
                     extent[1] - width / zf / 2 + xoffset,
                     extent[2] + height / zf / 2 + yoffset,
                     extent[3] - height / zf / 2 + yoffset)
        map_it(rgbdata, tifproj=projection, mapextent=mapextent, shapefile=wd + shapefile, plotfile=plotdir + plotfile,
                plottitle=title)

        #######################################
        # Zoom in to the centre
        #######################################
        plotfile = allscenes[x].split('.')[0] + '_map3.jpg'
        title = allscenes[x].split('.')[0]
        # zoom in to the centre (negative values zoom out, positive zoom in)
        zf = 4
        # offsets in map coordinates
        width = extent[1] - extent[0]
        height = extent[3] - extent[2]
        xoffset = 0
        yoffset = 0
        # need to unpack the tuple 'extent' and create a new tuple 'mapextent'
        mapextent = (extent[0] + width / zf / 2 + xoffset,
                     extent[1] - width / zf / 2 + xoffset,
                     extent[2] + height / zf / 2 + yoffset,
                     extent[3] - height / zf / 2 + yoffset)
        map_it(rgbdata, tifproj=projection, mapextent=mapextent, shapefile=wd + shapefile, plotfile=plotdir + plotfile,
                plottitle=title)

        #######################################
        # Zoom in to the top right corner
        #######################################
        plotfile = allscenes[x].split('.')[0] + '_map4.jpg'
        title = allscenes[x].split('.')[0]
        # zoom in to the top right corner (negative values zoom out, positive zoom in)
        zf = 2
        # offsets in map coordinates
        width = extent[1] - extent[0]
        height = extent[3] - extent[2]
        xoffset = round(width / zf / 2)
        yoffset = round(height / zf / 2)
        # need to unpack the tuple 'extent' and create a new tuple 'mapextent'
        mapextent = (extent[0] + width / zf / 2 + xoffset,
                     extent[1] - width / zf / 2 + xoffset,
                     extent[2] + height / zf / 2 + yoffset,
                     extent[3] - height / zf / 2 + yoffset)
        map_it(rgbdata, tifproj=projection, mapextent=mapextent, shapefile=wd + shapefile, plotfile=plotdir + plotfile,
                plottitle=title)

