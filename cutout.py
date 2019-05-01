#!/usr/bin/env python3
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# cutoutslink.py
#
# Generates on-the-fly cutouts for ATLASmultiID.py
# Requires radio surface brightness, radio RMS map, and optical images
# 
# Cutouts are radio contours, preprojected (via interpolation) onto heatmap 
# optical images. 
#
# Author:
#   Jesse Swan 
#   University of Tasmania
#   Aug 2016
#
#   mcvcm.py adapted for the GLEAM 4-Jy Sample, and now MIGHTEE-COSMOS:
#   Sarah White (svw26)
#   ICRAR/Curtin University --> SARAO/Rhodes University
#   Nov 2017 --> May 2019
#
# 19th Aug - Fixed crashing when optical mosaic slice wasn't square, or size 
#            (0,0) due to being in a region where optical mosaic doesn't 
#            cover. Optical array is now positionally inserted into an array 
#            of zeros of the required shape.
#
# Sarah's edits:
# 15th Dec 2017 - Making use of Tom Mauch's method for calculating the local rms
#                 of the radio image (rather than using a separate rms map).
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


from __future__ import division
from __future__ import print_function

import time
import warnings

import astropy.wcs as wcs
import matplotlib.pyplot as plt
import scipy.ndimage as ndimage   ### Added by svw26
import numpy as np
import reproject
from astropy.io import fits
from astropy.utils.exceptions import AstropyWarning

warnings.filterwarnings('ignore', category=AstropyWarning, append=True)
warnings.filterwarnings('ignore', category=RuntimeWarning)
# matplotlib.rcParams.update({'figure.autolayout': True})

verbose = False

# ------------------------------------------ #

if verbose:
    def verboseprint(*args):
        """
            usage: verboseprint('words', value, 'words', ...)
        """
        for arg in args:
            print(arg, end=' ')
        print()
else:  # a function that returns None
    def verboseprint(*args):
        return None


# http://preshing.com/20110924/timing-your-code-using-pythons-with-statement/
class Timer(object):
    '''
        Times imbedded code execution
        Example usage for averaging over 10 runs:

        ts = []
        for i in range(10):
            with Timer() as t:
                <RUN CODE>
                ts.append(t.interval)
        print 'mean was', np.mean(ts)
    '''
    def __enter__(self):
        self.start = time.clock()
        return self

    def __exit__(self, *args):
        self.end = time.clock()
        self.interval = self.end - self.start

# ------------------------------------------ #
# svw26: This function, for calculating the local rms, is courtesy of Tom Mauch
def get_background_variance(data,sigma_clip=5.0,tolerance=0.01):
    """Compute the variance by iteratively removing outliers greater than a given sigma
    until the mean changes by no more than tolerance.

    Inputs
    ------
    data - 1d numpy array of data to compute variance
    sigma_clip - the amount of sigma to clip the data before the next iteration
    tolerance - the fractional change in the mean to stop iterating

    Outputs
    -------
    variance - the final background variance in the sigma clipped image
    """
    #Initialise diff and data_clip and mean and std
    diff = 1
    mean = np.nanmean(data)
    data_clip = data
    while diff > tolerance:
        data_clip = data_clip[np.abs(data_clip)<mean+sigma_clip*np.nanstd(data_clip)]
        newmean = np.nanmean(data_clip)
        diff = np.abs(mean-newmean)/(mean+newmean)
        mean = newmean
    return np.nanvar(data_clip)
# ------------------------------------------ #


def rms(arr):
    '''
        find the RMS of input array
    '''
    from math import sqrt
    if len(arr.shape) > 1:
        arr = arr.flatten()
    return sqrt(old_div(np.nansum([x*x for x in arr]),len(arr)))


def arr_slice(arr, slicer, size):
    """
        Slices a 2d array to a square region specified by
        the slicer, and pads if necessary.

        Slicer should be defined as
               slicer = np.s_[xmin:xmax, ymin:ymax]

        Note:
        if array isn't square (xmax - xmin = ymax - ymin). If this occurs the returned array will be padded with zeroes
    """
    sliced = arr[slicer]
    if sliced.shape[0]!=sliced.shape[1]:
        # directly insert sliced data into an array of the intended size filled with 0.
        temp = np.zeros((size,size))
        temp[:sliced.shape[0], :sliced.shape[1]] = sliced
        sliced = temp
    return sliced


def cutouts2(infrared_mosaic, radio_image, radio_rms, targetRA, targetDEC, isize=200, rsize=180, vmax=1.5,
             verbose=False):   ### svw26: Note that vmax may need to be changed here, depending on the data
    """

    :param infrared_mosaic: asklujdhlkjhasdh
    :param radio_image: asdljhaskljhda
    :param radio_rms: asdioahsopd;a
    :param targetRA:
    :param targetDEC:
    :param isize:
    :param rsize:
    :param vmax:
    :param verbose:
    :return:
    """
    from matplotlib.colors import PowerNorm  # ,LogNorm, SymLogNorm,
    from astropy.nddata.utils import Cutout2D

    #if fits.getdata(radio_image)[0][0].shape != fits.getdata(radio_rms)[0][0].shape:   # svw26: Not actually using radioRMS maps
    #    raise Exception('Check that the radio image and radio rms files match')

    target_radec = (targetRA, targetDEC)

    # Work out the integer pixel position of the target coordinates in optical
    imap_full = wcs.WCS(infrared_mosaic)
    ipix = imap_full.wcs_world2pix([target_radec], 1)  # wcs conversions take list of lists
    ipix = [int(x) for x in ipix[0]]  # ensure returned pixels are integer

    verboseprint('o_full shape', fits.getdata(infrared_mosaic).shape)
    verboseprint('optical pix center', ipix)

    # Work out the integer pixel position of the target coordinates in radio
    rmap_full = wcs.WCS(radio_image).celestial
    rpix = rmap_full.wcs_world2pix([target_radec], 1)
    rpix = [int(x) for x in rpix[0]]

    verboseprint('r_full shape', fits.getdata(radio_image).shape)
    verboseprint('radio pix center', rpix)

    icut = Cutout2D(fits.getdata(infrared_mosaic), ipix, (isize, isize), mode='partial', fill_value=0.,
                    wcs=wcs.WCS(infrared_mosaic).celestial)
    imap = icut.wcs

    rcut = Cutout2D(fits.getdata(radio_image)[0][0], rpix, (rsize, rsize), mode='partial', fill_value=0.,
                    wcs=wcs.WCS(radio_image).celestial)
    rmap = rcut.wcs

    # svw26: Contours previously in steps of (2^n)*(2.5*median(local_rms))
    #contours = [2 ** x for x in range(17)]
    #rms_cut = Cutout2D(fits.getdata(radio_rms)[0][0], rpix, (rsize, rsize), mode='partial', fill_value=np.nan)  # svw26: requires radioRMS maps
    #rmap = rcut.wcs
    #local_rms = 2.5 * np.nanmedian(rms_cut.data.flatten())
    #contours = [local_rms * x for x in contours]

    ### Added by svw26
    data = pyfits.getdata(radio_image)
    local_rms = np.sqrt(get_background_variance(data.flatten()))  # svw26: New method, using Tom Mauch's functions for calculating the local rms
    print('local_rms = ',local_rms)  # svw26: for de-bugging, when no radio contours display...
    print('radio_image = ',radio_image)  # svw26: for de-bugging, when no radio contours display...
    highest_number_of_sigma = np.nanmax(data)/local_rms
    use_this_highest_power = math.floor(math.log(highest_number_of_sigma,2))
    contours = 3*local_rms*np.logspace(0,use_this_highest_power,num=use_this_highest_power+1,base=2.0)
    print('contours = ',contours)  # svw26: for de-bugging, when no radio contours display...

    # project radio coordinates (rcut,rmap) onto optical projection omap
    # Fails unless you specifying the shape_out (to be the same as what you are projecting onto)
    # Since omap doesn't have a .shape, ocut.shape is used instead

    project_r, footprint = reproject.reproject_interp((rcut.data, rmap), imap, shape_out=icut.data.shape)

    figure = plt.figure()  # figsize=(6.55, 5.2))
    axis = figure.add_subplot(111, projection=imap)
    # fig.subplots_adjust(left=0.25, right=.60)

    axtrans = axis.get_transform(
        'fk5')  # necessary for scattering data on later -- e.g ax.plot(data, transform=axtrans)

    ### svw26: Seeing whether a Gaussian smoothing of the reprojected radio-data leads to better contours. Yep, it does.
    #project_r = ndimage.gaussian_filter(project_r, sigma=(4.5, 4.5), order=0) 

    #### CHANGE VMAX HERE TO SUIT YOUR DATA - (I just experimented) #####
    # plotting
    normalise = PowerNorm(gamma=.7)
    axis.imshow(icut.data, origin='lower', cmap='gist_heat_r', norm=normalise,
                vmax=vmax)  # origin='lower' for .fits files
    axis.contour(np.arange(project_r.shape[0]), np.arange(project_r.shape[1]), project_r, levels=contours,
                 linewidths=0.8)

    axis.set_autoscale_on(False)
    axis.coords['RA'].set_axislabel('Right Ascension')
    axis.coords['DEC'].set_axislabel('Declination')

    return figure, axis, axtrans, imap


### svw26: What is different between cutouts(), below, and cutouts2(), above?
def cutouts(infrared_mosaic, radio_image, radio_rms, targetRA, targetDEC, isize=200, rsize=180, vmax=1.5,
            verbose=False):   ### svw26: Note that vmax may need to be changed here, depending on the data
    """

    :param infrared_mosaic: asklujdhlkjhasdh
    :param radio_image: asdljhaskljhda
    :param radio_rms: asdioahsopd;a
    :param targetRA:
    :param targetDEC:
    :param isize:
    :param rsize:
    :param vmax:
    :param verbose:
    :return:
    """
    from matplotlib.colors import PowerNorm  # ,LogNorm, SymLogNorm,

    if fits.getdata(radio_image)[0][0].shape != fits.getdata(radio_rms)[0][0].shape:
        raise Exception('Check that the radio image and radio rms files match')

    target = [targetRA, targetDEC]

    # Work out the integer pixel position of the target coordinates in optical
    imap_full = wcs.WCS(infrared_mosaic)
    ipix = imap_full.wcs_world2pix([target], 1)  # wcs conversions take list of lists
    ipix = [int(x) for x in ipix[0]]  # ensure returned pixels are integer

    verboseprint('o_full shape', fits.getdata(infrared_mosaic).shape)
    verboseprint('optical pix center', ipix)

    # Work out the integer pixel position of the target coordinates in radio
    rmap_full = wcs.WCS(radio_image).celestial
    rpix = rmap_full.wcs_world2pix([target],1)
    rpix = [int(x) for x in rpix[0]]

    verboseprint('r_full shape', fits.getdata(radio_image).shape)
    verboseprint('radio pix center', rpix)

    # Create slicer and slice the optical image, and optical WCS map
    half_isize = int(isize / 2.)
    oslicer = np.s_[ipix[1] - half_isize:ipix[1] + half_isize,
              ipix[0] - half_isize:ipix[0] + half_isize]  # (DEC:RA)

    icut = arr_slice(fits.getdata(infrared_mosaic), oslicer, isize)
    omap = imap_full[oslicer]  # Note: wcs map can't be sliced by arr_slice, do it manually
    verboseprint('ocut shape', icut.shape)

    # Create slicer and slice the radio image, radio rms, and radio WCS map
    half_rsize = int(rsize / 2.)
    rslicer = np.s_[rpix[1] - half_rsize:rpix[1] + half_rsize,
              rpix[0] - half_rsize:rpix[0] + half_rsize]  # (DEC:RA)

    rcut = arr_slice(fits.getdata(radio_image)[0][0], rslicer,
                     rsize)  # [0][0] because data is stored weird in fits file (shape (1,1,n,m))
    rmap = rmap_full[rslicer]
    verboseprint('rcut shape', rcut.shape)

    # Contours are to be in steps of (2^n)*(2.5*median(local_rms))
    contours = [2 ** x for x in range(17)]
    local_rms = 2.5 * np.nanmedian(
            fits.getdata(radio_rms)[0][0][rslicer])  # should have same shape and projecion as radio_image
    contours = [local_rms * x for x in contours]

    # project radio coordinates (rcut,rmap) onto optical projection omap
    # Fails unless you specifying the shape_out (to be the same as what you are projecting onto)
    # Since omap doesn't have a .shape, ocut.shape is used instead

    project_r, footprint = reproject.reproject_interp((rcut, rmap), omap, shape_out=icut.shape)

    figure = plt.figure()  # figsize=(6.55, 5.2))
    axis = figure.add_subplot(111, projection=omap)
    # fig.subplots_adjust(left=0.25, right=.60)

    axtrans = axis.get_transform(
            'fk5')  # necessary for scattering data on later -- e.g ax.plot(data, transform=axtrans)

    #### CHANGE VMAX HERE TO SUIT YOUR DATA - (I just experimented) #####
    # plotting
    normalise = PowerNorm(gamma=.7)
    axis.imshow(icut, origin='lower', cmap='gist_heat_r', norm=normalise, vmax=vmax)  # origin='lower' for .fits files
    axis.contour(np.arange(project_r.shape[0]), np.arange(project_r.shape[1]), project_r, levels=contours,
                 linewidths=0.8)

    axis.set_autoscale_on(False)
    axis.coords['RA'].set_axislabel('Right Ascension')
    axis.coords['DEC'].set_axislabel('Declination')

    return figure, axis, axtrans, omap


if __name__ == '__main__':
    ''' Test '''

    ## ELAIS test files for testing ##
    radio = 'data/ELAIS/ELAISmosaic_allch_8March2015.fits'
    noise = 'data/ELAIS/ELAISmosaic_allch_noise_8March2015.fits'
    swire = 'data/ELAIS/elais_mosaic.fits'
    optic = 'data/ELAIS/optical-r-mosaic.fits'
    target = [8.588891, -43.333966]
    # target = [8.740639, -43.919979]
    fig, ax, axtrans, omap = cutouts(swire, radio, noise, target[0], target[1], isize=200, rsize=110, verbose=True)
    sources, = ax.plot(target[0], target[1], 'k*', transform=axtrans)
    fig, ax, axtrans, omap = cutouts(optic, radio, noise, target[0], target[1], isize=400, rsize=210, vmax=40.5,
                                     verbose=True)
    sources, = ax.plot(target[0], target[1], 'k*', transform=axtrans)
    # sources.remove()

    plt.show()
