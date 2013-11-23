#!/usr/stsci/pyssg/Python-2.7/bin/python

# Developed by N.P.M. Kuin (MSSL/UCL)

__version__ = '1.0.0 20131023' 
import sys
import optparse
import numpy as np
import pylab as plt
try: 
   from astropy import fits as pyfits
except:   
   import pyfits
import re
import warnings
try:
  import imagestats
except: 
  import stsci.imagestats as imagestats  
import scipy
from scipy import interpolate
from scipy.ndimage import convolve
from scipy.signal import boxcar
from scipy.optimize import leastsq
from numpy import polyfit, polyval
try:
  from uvotpy import uvotplot,uvotmisc,uvotwcs,rationalfit,mpfit,uvotio
except:
  pass  
from uvotmisc import interpgrid, uvotrotvec
import uvotplot
import datetime
import os

if __name__ != '__main__':
   
      anchor_preset = list([None,None])
      bg_pix_limits = list([-100,-70,70,100])
      bg_lower_ = list([None,None])  # (offset, width) in pix, e.g., [20,30], default [50,50]
      bg_upper_ = list([None,None])  # (offset, width) in pix, e.g., [20,30], default [50,50]
      offsetlimit = None   

      #set Global parameters

      status = 0
      do_coi_correction = True  # if not set, disable coi_correction
      tempnames = list()
      tempntags = list()
      cval = -1.0123456789
      interactive = True
      update_curve = True
      contour_on_img = False
      give_result = False # with this set, a call to getSpec returns all data 
      use_rectext = False
      background_method = 'boxcar'  # alternatives 'splinefit' 'boxcar'
      background_smoothing = [50,7]   # 'boxcar' default smoothing in dispersion and across dispersion in pix
      trackwidth = 2.5  # width of extraction region in sigma  (alternative default = 1.0) 2.5 was used for flux calibration.
      bluetrackwidth = 1.3 # multiplier width of non-order-overlapped extraction region [not yet active]
      write_RMF = False
      background_source_mag = 18.0
      zeroth_blim_offset = 1.0

today_ = datetime.date.today()   
datestring = today_.isoformat()[0:4]+today_.isoformat()[5:7]+today_.isoformat()[8:10]


def getSpec(RA,DEC,obsid, ext, indir='./', wr_outfile=True, \
      outfile=None, calfile=None, fluxcalfile=None, \
      use_lenticular_image=True,
      offsetlimit=None, anchor_offset=None, anchor_position=[None,None],\
      background_lower=[None,None], background_upper=[None,None], \
      fixed_angle=None, spextwidth=13, curved="update",\
      fit_second=False, predict2nd=True, skip_field_src=False,      \
      optimal_extraction=False, catspec=None,write_RMF=write_RMF,\
      get_curve=False,fit_sigmas=True,get_sigma_poly=False,\
      lfilt1=None, lfilt1_ext=None, lfilt2=None, lfilt2_ext=None,  \
      wheelpos=None, interactive=interactive,  sumimage=None, set_maglimit=None,\
      plot_img=True, plot_raw=True, plot_spec=True, zoom=True, highlight=False, \
      clobber=False, chatter=1 ):
      
   '''Makes all the necessary calls to reduce the data. 
   
   Parameters
   ----------
   ra, dec : float
      The Sky position (J2000) in **decimal degrees**
      
   obsid : str
      The observation ID number as a **String**. Typically that is 
      something like "00032331001" and should be part of your 
      grism filename which is something like "sw00032331001ugu_dt.img"
      
   ext : int
      number of the extension to process         
   
   kwargs : dict
      optional keyword arguments, possible values are:

      - **fit_second** : bool
	
        fit the second order. Off since it sometimes causes problems when the
        orders overlap completely. Useful for spectra in top part detector
     
      - **background_lower** : list
	
        instead of default background list offset from spectrum as list 
        of two numbers, like [20, 40]. Distance relative to spectrum 
     
      - **background_upper** : list
	
        instead of default background list offset from spectrum as list 
        of two numbers, like [20, 40]. Distance relative to spectrum 
     
      - **offsetlimit** : int
	
        when strong spectrum lies next to target, feed offsetlimit a value.
        can be positive or negative. Try small numbers like -1, or 3, etc.
	
      - **wheelpos**: {160,200,955,1000}
        
	filter wheel position for the grism filter mode used. Helpful for 
	forcing Vgrism or UVgrism input when both are present in the directory.
	160:UV Clocked, 200:UV Nominal, 955:V clocked, 1000:V nominal 	
      
      - **zoom** : bool
	
        when False, the whole extracted region is displayed, including zeroth 
        order when present. 
     
      - **clobber** : bool
	
        When True, overwrite earlier output (see also outfile)
	
      - **write_RMF** : bool
      
        When True, write the rmf file (will take extra time due to large matrix operations)	
     
      - **use_lenticular_image** : bool

        When True and a lenticular image is present, it is used. If False, 
	the grism image header WCS-S system will be used for the astrometry, 
	with an automatic call to uvotgraspcorr for refinement. 
	
      - **sumimage** : str
	
        Name summed image generated using ``sum_Extimage()``, will extract spectrum 
        from summed image.
     
      - **wr_outfile** : bool
	
        If False, no output file is written
     
      - **outfile** : path, str
	
        Name of output file, other than automatically generated.
       
      - **calfile** : path, str
	
        calibration file name 
     
      - **fluxcalfile** : path, str
	
        flux calibration file name  or "CALDB" or None 
               
      - **predict2nd** : bool
	
        predict the second order flux from the first. Overestimates in centre a lot.
     
      - **skip_field_src** : bool
	
        if True do not locate zeroth order positions. Can be used if 
        absence internet connection or USNO-B1 server causes problems.
      
      - **optimal_extraction** : bool, obsolete
	
        Do not use.Better results with other implementation.
     
      
      - **catspec** : path
	
        optional full path to the catalog specification file for uvotgraspcorr.
     
      - **get_curve** : bool
	
        option to supply the curvature coefficients of all orders by hand.
        implemented but not tested.
     
      - **fit_sigmas** : bool
	
        fit the sigma of trackwidths if True (not implemented, always on)
     
      - **get_sigma_poly** : bool
	
        option to supply the polynomial for the sigma (not implemented) 
     
      - **lfilt1**, **lfilt2** : str
	
        name if the lenticular filter before and after the grism exposure 
	(now supplied by fileinfo())
     
      - **lfilt1_ext**, **lfilt2_ext** : int 
	
        extension of the lenticular filter (now supplied by fileinfo())
               
      - **plot_img** : bool
	
        plot the first figure with the det image
     
      - **plot_raw** : bool
	
        plot the raw spectrum data 
     
      - **plot_spec** : bool
	
        plot the flux spectrum
     
      - **highlight** : bool
	
        add contours to the plots to highlight contrasts
     
      - **chatter** : int
	
        verbosity of program
	
      - **set_maglimit** : int	
      
        specify a magnitude limit to seach for background sources in the USNO-B1 catalog  
  
   Returns 
   -------   
   None, or compound data (Y0, Y1, Y2, Y3, Y4) which are explained in the code.
  
   Notes
   ----- 
   **Quick Start**
      `getSpec(ra,dec,obsid, ext,)`  
      should produce plots and output files
   
   **Which directory?**
   
   The program needs to be started from the CORRECT data directory. 
   The attitude file [e.g., "sw<OBSID>pat.fits" ]is needed! 
   A link or copy of the attitude file needs to be present in the directory 
   or "../../auxil/" directory as well.

   **Global parameters**

   These parameters can be reset, e.g., during a (i)python session, before calling getSpec.
  
   - **trackwidth** : float
     width spectral extraction in units of sigma. The default is trackwidth = 2.5
     The alternative default is trackwidth = 1.0 which gives better results for 
     weak sources, or spectra with nearby contamination. However, the flux 
     calibration and coincidence-loss correction give currently inconsistent 
     results. When using trackwidth=1.0, rescale the flux to match trackwidth=2.5
     which value was used for flux calibration and coincidence-loss correction.
  
   - **give_result** : bool
     set to False since a call to getSpec with this set will return all the 
     intermediate results.	See returns 
 
   When the extraction slit is set to be straight ``curved="straight"`` it cuts off the UV part of the 
   spectrum for spectra located in the top left and bottom right of the image. 
     
     
   History
   -------     
     Version 2011-09-22 NPMK(MSSL)  : handle case with no lenticular filter observation
     Version 2012-01-15 NPMK(MSSL)  : optimal extraction is no longer actively supported until further notice
     Version 2013-10-23 NPMK(MSSL)  : fixed bug so uvotgraspcorr gives same accuracy as lenticular filter 

   Example
   -------
   from uvotpy.uvotgetspec import getSpec
   from uvotpy import uvotgetspec
   import os, shutil
   indir1 =  os.getenv('UVOTPY') +'/test'  
   indir2 =  os.getcwd()+'/test/UVGRISM/00055900056/uvot/image'  
   shutil.copytree(indir1, os.getcwd()+'/test' )
   getSpec( 254.7129625, 34.3148667, '00055900056', 1, offsetlimit=1,indir=indir2, clobber=True )
   
'''
   #  (specfile, lfilt1_, lfilt1_ext_, lfilt2_, lfilt2_ext_, attfile), (method), \
   #  (Xphi, Yphi, date1), (dist12, ankerimg, ZOpos), expmap, bgimg, bg_limits_used, bgextra = Y0
   #
   #( (dis,spnet,angle,anker,anker2,anker_field,ank_c), (bg,bg1,bg2,extimg,spimg,spnetimg,offset), 
   #  (C_1,C_2,img),  hdr,m1,m2,aa,wav1 ) = Y1 
   #	     
   #fit,(coef0,coef1,coef2,coef3),(bg_zeroth,bg_first,bg_second,bg_third),(borderup,borderdown),apercorr,expospec=Y2	
   #
   #counts, variance, borderup, borderdown, (fractions,cnts,vars,newsigmas) = Y3
   #
   #wav2p, dis2p, flux2p, qual2p, dist12p = Y4[0]
   #	   	 
   #     where, 
   #     
   #(present0,present1,present2,present3),(q0,q1,q2,q3), \
   #  (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
   #  (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
   #  (x,xstart,xend,sp_all,quality)  = fit     
   #     
   #     dis = dispersion with zero at ~260nm[UV]/420nm[V] ; spnet = background-substracted spectrum from 'spnetimg'
   #     angle  = rotation-angle used to extract 'extimg'  ; anker = first order anchor position in DET coordinates
   #     anker2 = second order anker X,Y position 	       ; anker_field = Xphi,Yphy input angles with respect to reference  
   #     ank_c  = X,Y position of axis of rotation (anker) in 'extimg'    
   #     bg = mean background, smoothed, with sources removed 
   #     bg1 = one-sided background, sources removed, smoothed ; bg2 = same for background opposite side
   #     extimg = image extracted of source and background, 201 pixels wide, all orders.
   #     spimg = image centered on first order position    ; spnetimg = background-subtracted 'spimg'
   #     offset = offset of spectrum from expected position based on 'anchor' at 260nm[UVG]/420nm[VG], first order
   #     C_1 = dispersion coefficients [python] first order; C_2 = same for second order
   #     img = original image                              ;
   #     WC_lines positions for selected WC star lines     ; hdr = header for image	  
   #     m1,m2 = index limits spectrum                     ; aa = indices spectrum (e.g., dis[aa])
   #     wav1 = wavelengths for dis[aa] first order (combine with spnet[aa])
   #     
   #     when wr_outfile=True the program produces a flux calibrated output file by calling uvotio. 
   #     [fails if output file is already present and clobber=False] 
   #     
   #     The background must be consistent with the width of the spectrum summed. 
   
   from uvotio import fileinfo, rate2flux
   
   # check environment
   CALDB = os.getenv('CALDB')
   if CALDB == '': 
      print 'WARNING: The CALDB environment variable has not been set'
   
   HEADAS = os.getenv('HEADAS')
   if HEADAS == '': 
      print 'WARNING: The HEADAS environment variable has not been set'
      print 'That is needed for the calls to uvot Ftools '
   
   SCAT_PRESENT = os.system('which scat > /dev/null')
   if SCAT_PRESENT != 0:
      print 'WARNING: cannot locate the scat program \nDid you install WCSTOOLS ?\n'
      
   SESAME_PRESENT = os.system('which sesame > /dev/null')
   if SESAME_PRESENT != 0:
      print 'WARNING: cannot locate the sesame program \nDid you install the cdsclient tools?\n'   


   # fix some parameters 
   framtime = 0.0110322
   splineorder=3
   getzmxmode='spline'
   smooth=50
   testparam=None
   msg = "" ; msg2 = ""
   attime = datetime.datetime.now()
   logfile = 'uvotgrism_'+obsid+'['+str(ext)+']'+'_'+attime.isoformat()[0:19]+'.log'
   if type(fluxcalfile) == bool: fluxcalfile = None
   tempnames.append(logfile)
   tempntags.append('logfile')
   tempnames.append('rectext_spectrum.img')
   tempntags.append('rectext')
   lfiltnames=np.array(['uvw2','uvm2','uvw1','u','b','v','wh'])
   ext_names =np.array(['uw2','um2','uw1','uuu','ubb','uvv','uwh'])
   filestub = 'sw'+obsid
   histry = ""
   for x in sys.argv: histry += x + " "
   Y0 = None
   Y2 = None
   Y3 = None
   Y4 = None
   lfilt1_aspcorr = "not initialized"
   lfilt2_aspcorr = "not initialized"
   
   if sumimage == None:
      try:
        ext = int(ext)
      except:
        print "fatal error in extension number: must be an integer value"	
   
      # locate related lenticular images 
      specfile, lfilt1_, lfilt1_ext_, lfilt2_, lfilt2_ext_, attfile = \
          fileinfo(filestub,ext,directory=indir,wheelpos=wheelpos,chatter=chatter) 

      # set some flags and variables
      lfiltinput = (lfilt1 != None) ^ (lfilt2 != None) 
      lfiltpresent = lfiltinput | (lfilt1_ != None) | (lfilt2_ != None) 
      if (lfilt1_ == None) & (lfilt2_ == None): 
         # ensure the output is consistent with no lenticular filter solution
         use_lenticular_image = False
    
      lfiltflag = False    
      if ((lfilt1 == None)&(lfilt1_ != None)): 
         lfilt1 = lfilt1_   
         lfilt1_ext = lfilt1_ext_
         if chatter > 0: print "lenticular filter 1 from search lenticular images"
         lfiltflag = True
	 lfilt1_aspcorr = None
	 try: 
	   hdu_1 = pyfits.getheader(indir+"/sw"+obsid+"u"+lfilt1[-2:]+"_sk.img",lfilt1_ext)
	   lfilt1_aspcorr = hdu_1["ASPCORR"]  
	 except:
	   hdu_1 = pyfits.getheader(indir+"/sw"+obsid+"u"+lfilt1[-2:]+"_sk.img.gz",lfilt1_ext)
	   lfilt1_aspcorr = hdu_1["ASPCORR"]  
      if ((lfilt2 == None)&(lfilt2_ != None)):
         lfilt2 = lfilt2_
         lfilt2_ext = lfilt2_ext_    
         if chatter > 0: print "lenticular filter 2 from search lenticular images"
         lfiltflag = True
	 lfilt2_aspcorr = None
	 try: 
	   hdu_2 = pyfits.getheader(indir+"/sw"+obsid+"u"+lfilt2[-2:]+"_sk.img",lfilt2_ext)
	   lfilt2_aspcorr = hdu_2["ASPCORR"]  
	 except:
	   hdu_2 = pyfits.getheader(indir+"/sw"+obsid+"u"+lfilt2[-2:]+"_sk.img.gz",lfilt2_ext)
	   lfilt2_aspcorr = hdu_2["ASPCORR"]  

      # report       
      if chatter > 4:
         msg2 += "getSpec: image parameter values\n"
         msg2 += "ra, dec = (%6.1f,%6.1f)\n" % (RA,DEC)
         msg2 += "filestub, extension = %s[%i]\n"% (filestub, ext)
	 if lfiltpresent & use_lenticular_image:
             msg2 += "first/only lenticular filter = "+lfilt1+" extension first filter = "+str(lfilt1_ext)+'\n'
	     msg2 += "   Aspect correction keyword : %s\n"%(lfilt1_aspcorr)
             if lfilt2_ext != None: 
	         msg2 += "second lenticular filter = "+lfilt2+" extension second filter = "+str(lfilt2_ext)+'\n'
	         msg2 += "   Aspect correction keyword : %s\n"%(lfilt2_aspcorr)
	 if not use_lenticular_image:
	     msg2 += "anchor position derived without lenticular filter\n"	 
         msg2 += "spectrum extraction preset width = "+str(spextwidth)+'\n'
         #msg2 += "optimal extraction "+str(optimal_extraction)+'\n'
      
      if chatter > -1:
           msg += '\nuvotgetspec version : '+__version__+'\n'
           msg += ' Position RA,DEC  : '+str(RA)+' '+str(DEC)+'\n'
           msg += ' grism file       : '+specfile+'['+str(ext)+']\n'
           msg += ' attitude file    : '+attfile+'\n'
	   if lfiltpresent & use_lenticular_image:
	      if ((lfilt1 != None) & (lfilt1_ext != None)): 
	         msg += ' lenticular file 1: '+lfilt1+'['+str(lfilt1_ext)+']\n'
		 msg += '           aspcorr: '+lfilt1_aspcorr+'\n'
	      if ((lfilt2 != None) & (lfilt2_ext != None)):
	         msg += ' lenticular file 2: '+lfilt2+'['+str(lfilt2_ext)+']\n'
		 msg += '           aspcorr: '+lfilt2_aspcorr+'\n'
	   if not use_lenticular_image:
	      msg += "anchor position derived without lenticular filter\n"	 

      hdr = pyfits.getheader(specfile,int(ext))

      tstart = hdr['TSTART']
      tstop  = hdr['TSTOP'] 
      wheelpos = hdr['WHEELPOS']
      expo     = hdr['EXPOSURE']
      expmap   = [hdr['EXPOSURE']]
      try:
        framtime = hdr['framtime']
      except: 
        # compute the frametime from the CCD deadtime and deadtime fraction 
        deadc = hdr['deadc']
        deadtime = 600*285*1e-9 # 600ns x 285 CCD lines seconds
        framtime = deadtime/(1.0-deadc)
        hdr.update('framtime',framtime,comment='frame time computed from deadc ')
        pass
      #if not hdr.has_key('detnam'):
      if not 'detnam' in hdr:
        hdr.update('detnam',str(hdr['wheelpos']))    
     
      msg += ' exposuretime    : %7.1f \n'%(expo)  
      maxcounts = 1.1 * expo/framtime 

      if chatter > 0:
           msg += ' wheel position   : '+str(wheelpos)+'\n'
           msg += '======================================\n'
	
      try: 
         if ( (np.abs(RA - hdr['RA_OBJ']) > 0.4) ^ (np.abs(DEC - hdr['DEC_OBJ']) > 0.4) ): 
            sys.stderr.write("\nWARNING:  It looks like the input RA,DEC and target position in header are different fields\n")	  
	 	
      except (RuntimeError, TypeError, NameError, KeyError):
         pass 
         msg2 += " cannot read target position from header for verification\n"	
       
      if lfiltinput:
         #  the lenticular filter(s) were specified on the command line.
         #  check that the lenticular image and grism image are close enough in time.
         if lfilt1_ext == None: 
            lfilt1_ext = int(ext)
         lpos = np.where( np.array([lfilt1]) == lfiltnames )
         if len(lpos[0]) < 1: sys.stderr.write("WARNING: illegal name for the lenticular filter\n")
         lnam = ext_names[lpos]   
         lfile1 = filestub+lnam[0]+'_sk.img'   
         hdr_l1 = pyfits.getheader(lfile1,lfilt1_ext)
         tstart1 = hdr_l1['TSTART']
         tstop1  = hdr_l1['TSTOP'] 
         if not ( (np.abs(tstart-tstop1) < 20) ^  (np.abs(tstart1-tstop) < 20) ): 
            sys.stderr.write("WARNING:  check that "+lfile1+" matches the grism image\n")   
         if lfilt2 != None:        
           if lfilt2_ext == None: 
              lfilt2_ext = lfilt1_ext+1
           lpos = np.where( np.array([lfilt2]) == lfiltnames )
           if len(lpos[0] < 1): sys.stderr.write("WARNING: illegal name for the lenticular filter\n")
           lnam = ext_names[lpos]   
           lfile2 = filestub+lnam[0]+'_sk.img'   
           hdr_l2 = pyfits.getheader(lfile1,lfilt1_ext)         
           tstart2 = hdr_l2['TSTART']
           tstop2  = hdr_l2['TSTOP'] 
           if not ( (np.abs(tstart-tstop1) < 20) ^  (np.abs(tstart1-tstop) < 20) ): 
              sys.stderr.write("WARNING:  check that "+lfile2+" matches the grism image\n")   

      if (not lfiltpresent) | (not use_lenticular_image):  
         method = "grism_only"
      else: 
         method = None   
	 
      # retrieve the input angle relative to the boresight	 
      Xphi, Yphi, date1 = findInputAngle( RA, DEC, filestub, ext, \
           wheelpos=wheelpos, lfilter=lfilt1, lfilter_ext=lfilt1_ext, lfilt2=lfilt2, lfilt2_ext=lfilt2_ext, \
	   method=method, attfile=attfile, catspec=catspec, indir=indir, chatter=chatter)

      # read the anchor and dispersion out of the wavecal file  	      
      anker, anker2, C_1, C_2, angle, calibdat = getCalData(Xphi,Yphi,wheelpos, date1, \
         calfile=calfile, chatter=chatter)    
      msg += "first order anchor position on detector in det coordinates:\n"
      msg += "anchor1=(%8.2f,%8.2f)\n" % (anker[0],anker[1])   
      msg += "first order dispersion polynomial (distance anchor, \n"
      msg += "   highest term first)\n"
      for k in range(len(C_1)):
         msg += "DISP1_"+str(k)+"=%12.4e\n" % (C_1[k])     
      msg += "second order anchor position on detector in det coordinates:\n"
      msg += "anchor2=(%8.2f,%8.2f)\n" % (anker2[0],anker2[1])   
      msg += "second order dispersion polynomial (distance anchor2,\n"
      msg += "   highest term first)\n"
      for k in range(len(C_2)):
         msg += "DISP2_"+str(k)+"=%12.4e\n" % (C_2[k])
      print "first order anchor = ",anker
      print "second order anchor = ",anker2	      
      print "first order dispersion = %s"%(str(C_1))
      print "second order dispersion = %s"%(str(C_2))
      # override angle
      if fixed_angle != None:
         msg += "WARNING: overriding calibration file angle for extracting \n\tspectrum cal: "+str(angle)+'->'+str(fixed_angle)+" \n" 
         angle = fixed_angle  
   
      # override anchor position in det pixel coordinates   
      if anchor_position[0] != None:
         cal_anker =  anker
         anker = np.array(anchor_position)
         msg += "overriding anchor position with value [%8.1f,%8.1f]\n" % (anker[0],anker[1])
         anker2 = anker2 -cal_anker + anker      
         msg += "overriding anchor position 2nd order with value [%8.1f,%8.1f]\n"%(anker2[0],anker2[1])

      anker_field = np.array([Xphi,Yphi])
      theta=np.zeros(5)+angle # use the angle from first order everywhere.
      C_0 = np.zeros(3)       # not in calibration file. Use uvotcal/zemax to get.
      C_3 = np.zeros(3)
      Cmin1 = np.zeros(3)
      msg += "field coordinates:\n"
      msg += "FIELD=(%9.4f,%9.4f)\n" % (Xphi,Yphi)
   
      # order distance between anchors 
      dist12 = np.sqrt( (anker[0]-anker2[0])**2 + (anker[1]-anker2[1])**2 )
      msg += "order distance 1st-2nd anchors :\n"
      msg += "DIST12=%7.1f\n" % (dist12)
   
      # determine x,y locations of certain wavelengths on the image
      # TBD: add curvature
      if wheelpos < 500: 
         wavpnt = np.arange(1700,6800,200)
      else:
         wavpnt = np.arange(2500,6600,200)   
      dispnt=pixdisFromWave(C_1,wavpnt) # pixel distance to anchor
   
      if chatter > 0: msg2 += 'first order angle at anchor point: = %7.1f\n'%(angle)        

      crpix = crpix1,crpix2 = hdr['crpix1'],hdr['crpix2']  
      crpix = np.array(crpix)   # centre of image
      ankerimg = anker - np.array([1100.5,1100.5])+crpix  
      xpnt = ankerimg[0] + dispnt*np.cos((180-angle)*np.pi/180)
      ypnt = ankerimg[1] + dispnt*np.sin((180-angle)*np.pi/180)
      msg += "1st order anchor on image at (%7.1f,%7.1f)\n"%(ankerimg[0],ankerimg[1])
   
      if chatter > 4: msg += "Found anchor point; now extracting spectrum.\n"
      if chatter > 2: print "==========Found anchor point; now extracting spectrum ========"
   
      if offsetlimit == None:
         if wheelpos > 300:
            offsetlimit = 9
	    sys.stdout.write("automatically set the value for the offsetlimit = "+str(offsetlimit)+'\n') 
   
   # provide some checks on background inputs:
   if background_lower[0] != None:
      background_lower =  np.abs(background_lower)
      if np.sum(background_lower) >= 190.0: 
         background_lower = [None,None]
	 msg += "WARNING: background_lower set too close to edge image\n          Using default\n"	 
   if background_upper[0] != None:
      background_upper =  np.abs(background_upper)
      if np.sum(background_upper) >= 190.0: 
         background_upper = [None,None]
	 msg += "WARNING: background_upper set too close to edge image\n          Using default\n"	 

   #  find background, extract straight slit spectrum

   if sumimage != None:
      # initialize parameters for extraction summed extracted image    
      print 'reading summed image file : '+sumimage
      print 'ext label for output file is set to : ', ext
      Y6 = sum_Extimage (None, sum_file_name=sumimage, mode='read')
      extimg, expmap, exposure, wheelpos, C_1, C_2, dist12, anker, \
      (coef0, coef1,coef2,coef3,sig0coef,sig1coef,sig2coef,sig3coef), hdr = Y6
      tstart = hdr['tstart']
      ank_c = [100,500,0,2000]
      if offsetlimit == None:
        offset = 0
      else: 
        offset = offsetlimit  # for sumimage used offsetlimit to set the offset
	ank_c[0] = 96+offsetlimit 	
      dis = np.arange(-500,1500)
      img = extimg
      # get background
      bg, bg1, bg2, bgsig, bgimg, bg_limits_used, bgextra = findBackground(extimg,
         background_lower=background_lower,
         background_upper=background_upper,)
      skip_field_src = True
      spnet = bg1  # placeholder
      expo = exposure
      maxcounts = exposure/0.01
      anker2 = anker + [dist12,0]
      spimg,spnetimg,anker_field = None, None, (0.,0.)
      m1,m2,aa,wav1 = None,None,None,None
      if outfile == None: 
         outfile='sum_image_'
      	 	
       
   else:	
      (dis, spnet, bg, bg1, (bg2, bgsig, bgimg, bg_limits_used, bgextra), \
           extimg, spimg, spnetimg, offset, ank_c) = \
           extractSpecImg(specfile,ext,ankerimg,angle,spwid=spextwidth,\
	      background_lower=background_lower, background_upper=background_upper,
              offsetlimit=offsetlimit,  chatter=chatter)

      #msg += "1st order anchor offset from spectrum = %7.1f\n"%(offset)
      #msg += "anchor position in rotated extracted spectrum (%6.1f,%6.1f)\n"%(ank_c[1],ank_c[0])

      # curved == "straight"
   
      calibdat = None # should free the memory properly here. 	
   
      if chatter > 2: print "============ straight slit extraction complete ================="
		
      if np.max(spnet) < maxcounts: maxcounts = 2.0*np.max(spnet) 		

      # initial limits spectrum 
      m1 = ank_c[1]-400 
      if wheelpos > 500:     m1 = ank_c[1]-370 
      if m1 < 0: m1 = 0
      if m1 < (ank_c[2]+30): m1 = ank_c[2]+30
      m2 = ank_c[1]+2000 
      if wheelpos > 500: m2 = ank_c[1]+1000 
      if m2 >= len(dis): m2 = len(dis)-2
      if m2 > (ank_c[3]-40): m2=(ank_c[3]-40) 
      aa = range(int(m1),int(m2)) 
      wav1 = polyval(C_1,dis[aa])

      # get grism det image 
      img = pyfits.getdata(specfile, ext)

      try:
         offset = np.asscalar(offset)
      except:
         pass
      
      Zbg  = bg, bg1, bg2, bgsig, bgimg, bg_limits_used, bgextra
   net  = extimg-bgextra[-1]
   var  = extimg.copy()
   dims = np.asarray( img.shape )
   dims = np.array([dims[1],dims[0]])
   dims2 = np.asarray(extimg.shape)
   dims2 = np.array([dims2[1],dims2[0]])
   
   msg += "Lower background from y = %i pix\nLower background to y = %i pix\n" % (bg_limits_used[0],bg_limits_used[1])
   msg += "Upper background from y = %i pix\nUpper background to y = %i pix\n" % (bg_limits_used[2],bg_limits_used[3])
   msg += "TRACKWID=%4.1f\n" % (trackwidth)
   
   if (not skip_field_src) & (sumimage == None):
      if chatter > 2: print "================== locate zeroth orders due to field sources ============="
      ZOpos = find_zeroth_orders(filestub, ext, wheelpos,indir=indir,set_maglimit=set_maglimit,clobber="yes", )
      Xim,Yim,Xa,Yb,Thet,b2mag,matched,ondetector = ZOpos
      pivot_ori=np.array([(ankerimg)[0],(ankerimg)[1]])
   else:
      ZOpos = None   

   #    collect some results:
   if sumimage == None:
      Y0 = (specfile, lfilt1_, lfilt1_ext_, lfilt2_, lfilt2_ext_, attfile), (method), \
           (Xphi, Yphi, date1), (dist12, ankerimg, ZOpos), expmap, bgimg, bg_limits_used, bgextra
   else:
      Y0 = None, None, None, (dist12, None, None), expmap, bgimg, bg_limits_used, bgextra  
      angle = 0.0

   # curvature from input (TBD how - placeholder with raw_input)
   #  choose input coef or pick from plot
   #  choose order to do it for
   
   if get_curve & interactive:
      spextwidth = None
      # grab coefficients
      poly_1 = None
      poly_2 = None
      poly_3 = None
      try: 
         poly_1 = raw_input("give coefficients of first order polynomial array([X^3,X^2,X,C])")
         poly_2 = raw_input("give coefficients of second order polynomial array([X^2,X,C])")
         poly_3 = raw_input("give coefficients of third order polynomial array([X,C])")
      except:
         print "failed"
         
      fitorder, cp2, (coef0,coef1,coef2,coef3), (bg_zeroth,bg_first,\
	  bg_second,bg_third), (borderup,borderdown), apercorr, expospec, msg, curved \
       =  curved_extraction(extimg,ank_c,anker, wheelpos,ZOpos=ZOpos, predict_second_order=predict2nd,
             angle=angle,offset=offset,  poly_1=poly_1,poly_2=poly_2,poly_3=poly_3,
	     msg=msg, curved=curved, outfull=True, expmap=expmap, fit_second=fit_second, 
	     fit_third=fit_second, C_1=C_1,C_2=C_2,dist12=dist12, chatter=chatter) 
	 # fit_sigmas parameter needs passing 
	 
      (present0,present1,present2,present3),(q0,q1,q2,q3), \
              (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
              (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
	      (x,xstart,xend,sp_all,quality)  = fitorder
	      
      # update the anchor y-coordinate	      
      ank_c[0] = y1[ank_c[1]]	      
	      
		
   # curvature from calibration
   
   if spextwidth != None:
      
      fitorder, cp2, (coef0,coef1,coef2,coef3), (bg_zeroth,bg_first,\
	  bg_second,bg_third), (borderup,borderdown) , apercorr, expospec, msg, curved \
          =  curved_extraction(extimg,ank_c,anker, wheelpos, \
	     ZOpos=ZOpos, skip_field_sources=skip_field_src, \
	     background_lower=background_lower, background_upper=background_upper, \
             angle=angle,offset=offset,  outfull=True, expmap=expmap, \
	     msg = msg, curved=curved, fit_second=fit_second, 
	     fit_third=fit_second, C_1=C_1,C_2=C_2,dist12=dist12, chatter=chatter) 
	     
      (present0,present1,present2,present3),(q0,q1,q2,q3), \
          (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
          (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
	  (x,xstart,xend,sp_all,quality)  = fitorder
	
      # 2012-02-20 moved to curved_extraction so that updated track is used for spectrum 		 
      #if curved == "update":
      #  # the hope is, that with more data the calibration can be improved to eliminate this step
      #  #try:	 
      #    fitorder2, fval, fvalerr = updateFitorder(extimg, fitorder, wheelpos, full=True,
      #      predict2nd=predict2nd, fit_second=fit_second, fit_third=fit_second,
      #	    C_1=C_1, C_2=C_2, d12=dist12, chatter=chatter)	      
      #    msg += "updated fitorder\n"
      # 
      #    (present0,present1,present2,present3),(q0,q1,q2,q3), \
      #        (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
      #        (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
      #	      (x,xstart,xend,sp_all,quality)  = fitorder2
      #	      
      #    # update the anchor y-coordinate	      
      #    ank_c[0] = y1[ank_c[1]]	      
      #  #except:
      #	#  msg += "WARNING: fit order curvature update has failed\n"
      #	#  curved = "curve"	      
	 
      msg += "orders present:"
      if present0: msg += "0th order, "
      if present1: msg += "first order"
      if present2: msg += ", second order"
      if present3: msg += ", third order "
      
      msg += '\nparametrized order curvature:\n'	 
      if present0: 
         for k in range(len(coef0)):
            msg += "COEF0_"+str(k)+"=%12.4e\n" % (coef0[k])  
      if present1: 
         for k in range(len(coef1)):
            msg += "COEF1_"+str(k)+"=%12.4e\n" % (coef1[k])     
      if present2: 
         for k in range(len(coef2)):
	    msg += "COEF2_"+str(k)+"=%12.4e\n" % (coef2[k])     
      if present3: 
         for k in range(len(coef3)):
            msg += "COEF3_"+str(k)+"=%12.4e\n" % (coef3[k])
      
      msg += '\nparametrized width slit:\n'	 
      if present0: 
         for k in range(len(sig0coef)):
            msg += "SIGCOEF0_"+str(k)+"=%12.4e\n" % (sig0coef[k])  
      if present1: 
         for k in range(len(sig1coef)):
            msg += "SIGCOEF1_"+str(k)+"=%12.4e\n" % (sig1coef[k])     
      if present2: 
         for k in range(len(sig2coef)):
	    msg += "SIGCOEF2_"+str(k)+"=%12.4e\n" % (sig2coef[k])     
      if present3: 
         for k in range(len(sig3coef)):
            msg += "SIGCOEF3_"+str(k)+"=%12.4e\n" % (sig3coef[k])

   offset = ank_c[0]-100.0	      		
   msg += "best fit 1st order anchor offset from spectrum = %7.1f\n"%(offset)
   msg += "anchor position in rotated extracted spectrum (%6.1f,%6.1f)\n"%(ank_c[1],ank_c[0])
   
   #2012-02-20 moved updateFitorder to curved_extraction
   #if curved == "update": 
   #   fit = fitorder2   
   #else:
   #   fit = fitorder    
   fit = fitorder
    
   if optimal_extraction:
      print "Starting optimal extraction:  This can take a few minutes ......\n\t ........\n\t\t ............."
      Y3 = get_initspectrum(net,var,fit,160,ankerimg,C_1=C_1,C_2=C_2,dist12=dist12,
           predict2nd=predict2nd,
           chatter=1)
      
      counts, variance, borderup, borderdown, (fractions,cnts,vars,newsigmas) = Y3 
      
   # need to test that C_2 is valid here
   if predict2nd:
      Y4 = predict_second_order(dis,(sp_first-bg_first), C_1,C_2, dist12, quality,dlim1L, dlim1U,wheelpos) 
      wav2p, dis2p, flux2p, qual2p, dist12p = Y4[0]
      
   if interactive:
      import pylab as plt

      if (plot_img) & (sumimage == None):
         plt.winter()
         #   make plot of model on image [figure 1]
         #xa = np.where( (dis < 1400) & (dis > -300) )
         bga = bg.copy()
         fig1 = plt.figure(1); plt.clf()
         plt.imshow(np.log(img),vmin=np.log(bga.mean()*0.1),vmax=np.log(bga.mean()*4))
         levs = np.array([5,15,30,60,120,360]) * bg.mean()
         if highlight: plt.contour(img,levels=levs)
         #  plot yellow wavelength marker 
	 #  TBD : add curvature 
         plt.plot(xpnt,ypnt,'+k',markersize=14)
         if zoom:
            plt.xlim(np.max(np.array([0.,0.])),np.min(np.array([hdr['NAXIS1'],ankerimg[0]+400])))
	    plt.ylim(np.max(np.array([0.,ankerimg[1]-400 ])),   hdr['NAXIS2'])
	 if not skip_field_src:   
            uvotplot.plot_ellipsoid_regions(Xim,Yim,Xa,Yb,Thet,b2mag,matched,ondetector,pivot_ori,pivot_ori,dims,17.,)


      if (plot_raw):
         plt.winter()
         nsubplots = 4
	 if not fit_second: nsubplots=3
         #   make plot of spectrum [figure 2]
         fig2 = plt.figure(2); plt.clf()
	 
	 # image slice 
	 ax21 = plt.subplot(nsubplots,1,1)
	 ac = -ank_c[1]
	 plt.winter()
	 plt.imshow(np.log10(net),vmin=-0.8,vmax=0.8,extent=(ac,ac+extimg.shape[1],0,extimg.shape[0]) )
	 plt.contour(np.log10(net),levels=[1,1.3,1.7,2.0,3.0],extent=(ac,ac+extimg.shape[1],0,extimg.shape[0]))
	 #plt.imshow( extimg,vmin= (bg1.mean())*0.1,vmax= (bg1.mean()+bg1.std())*2, extent=(ac,ac+extimg.shape[1],0,extimg.shape[0]) )
         #levels = np.array([5,10,20,40,70,90.])
	 #levels = spnet[ank_c[2]:ank_c[3]].max()  * levels * 0.01		    		    
         #if highlight: plt.contour(net,levels=levels,extent=(ac,ac+extimg.shape[1],0,extimg.shape[0]))
         #  cross_section_plot: 
         cp2 = cp2/np.max(cp2)*100
         plt.plot(ac+cp2+ank_c[1],np.arange(len(cp2)),'k',lw=2,alpha=0.6,ls='steps')
	 # plot zeroth orders
         if not skip_field_src:
            pivot= np.array([ank_c[1],ank_c[0]-offset])
            #pivot_ori=ankerimg
            uvotplot.plot_ellipsoid_regions(Xim,Yim,Xa,Yb,Thet,b2mag,matched,ondetector,pivot,pivot_ori,dims2,17.,img_angle=angle-180.0,ax=ax21)
         # plot line on anchor location 
         plt.plot([ac+ank_c[1],ac+ank_c[1]],[0,200],'k',lw=2) 
	 # plot position centre of orders  
         if present0: plt.plot(ac+q0[0],y0[q0[0]],'k--',lw=1.2)
         plt.plot(             ac+q1[0],y1[q1[0]],'k--',lw=1.2)
         if present2: plt.plot(ac+q2[0],y2[q2[0]],'k--',alpha=0.6,lw=1.2)
         if present3: plt.plot(ac+q3[0],y3[q3[0]],'k--',alpha=0.3,lw=1.2)
	 # plot borders slit region
	 if present0:
            plt.plot(ac+q0[0],borderup  [0,q0[0]],'r-')
            plt.plot(ac+q0[0],borderdown[0,q0[0]],'r-')
	 if present1:   
            plt.plot(ac+q1[0],borderup  [1,q1[0]],'r-',lw=1.2)
            plt.plot(ac+q1[0],borderdown[1,q1[0]],'r-',lw=1.2)
	 if present2:   
            plt.plot(ac+q2[0],borderup  [2,q2[0]],'r-',alpha=0.6,lw=1)
            plt.plot(ac+q2[0],borderdown[2,q2[0]],'r-',alpha=0.6,lw=1)
	 if present3:   
            plt.plot(ac+q3[0],borderup  [3,q3[0]],'r-',alpha=0.3,lw=1.2)
            plt.plot(ac+q3[0],borderdown[3,q3[0]],'r-',alpha=0.3,lw=1.2)
	 # plot limits background
	 plt_bg = np.ones(len(q1[0]))
	 if (background_lower[0] == None) & (background_upper[0] == None):
	    background_lower = [0,50] ; background_upper = [150,200] 
	    plt.plot(ac+q1[0],plt_bg*(background_lower[1]),'-k',lw=1.5 ) 
	    plt.plot(ac+q1[0],plt_bg*(background_upper[0]),'-k',lw=1.5 )
	 else:   
	  if background_lower[0] != None:
	    plt.plot(ac+q1[0],plt_bg*(y1[ank_c[1]]-background_lower[0]),'-k',lw=1.5 )
	    plt.plot(ac+q1[0],plt_bg*(y1[ank_c[1]]-background_lower[1]),'-k',lw=1.5 ) 
	  elif background_lower[1] != None:
	    plt.plot(ac+q1[0],plt_bg*(background_lower[1]),'-k',lw=1.5 ) 	      
	  if background_upper[1] != None:     
	    plt.plot(ac+q1[0],plt_bg*(y1[ank_c[1]]+background_upper[0]),'-k',lw=1.5 )
	    plt.plot(ac+q1[0],plt_bg*(y1[ank_c[1]]+background_upper[1]),'-k',lw=1.5 )   
	  elif background_upper[0] != None:
	    plt.plot(ac+q1[0],plt_bg*(background_upper[0]),'-k',lw=1.5 )
	    
	 # rescale, title   
         plt.ylim(0,200)
	 if not zoom:
	    xlim1 = ac+ank_c[2]
	    xlim2 = ac+ank_c[3]            
	 else:
	    xlim1 = max(ac+ank_c[2], -420)
	    xlim2 = min(ac+ank_c[3],1400)
	 plt.xlim(xlim1,xlim2)
	 plt.title(obsid+'+'+str(ext))

         # first order raw data plot
	 ax22 = plt.subplot(nsubplots,1,2) 
	 plt.rcParams['legend.fontsize'] = 'small'
	 if curved == 'straight':
            p1, = plt.plot( dis[ank_c[2]:ank_c[3]], spnet[ank_c[2]:ank_c[3]],'k',ls='steps',lw=0.5,alpha=0.5,label='straight')
            p2, = plt.plot( dis[ank_c[2]:ank_c[3]], spextwidth*(bg1[ank_c[2]:ank_c[3]]+bg2[ank_c[2]:ank_c[3]])*0.5, 'b',alpha=0.5,label='background')
	    plt.legend([p1,p2],['straight','background'],loc=0,)
	 
	 if curved != "straight":
	    p3, = plt.plot(x[q1[0]],(sp_first-bg_first)[q1[0]],'r',ls='steps',label='spectrum') 	    
	    plt.plot(x[q1[0]],(sp_first-bg_first)[q1[0]],'k',alpha=0.2,ls='steps',label='_nolegend_') 	    
	    p7, = plt.plot(x[q1[0]], bg_first[q1[0]],'y',alpha=0.5,lw=1.1,ls='steps',label='background') 
	    #    bad pixels:	    
	    qbad = np.where(quality[q1[0]] > 0)
	    p4, = plt.plot(x[qbad],(sp_first-bg_first)[qbad],'xk',markersize=4)
	    #p7, = plt.plot(x[q1[0]],(bg_first)[q1[0]],'r-',alpha=0.3,label='curve_bkg') 
	    #    annotation
	    plt.legend([p3,p4,p7],['spectrum','suspect','background'],loc=0,)
	    maxbg = np.max(bg_first[q1[0]][np.isfinite(bg_first[q1[0]])])
	    topcnt = 1.2 * np.max([np.max(spnet[q1[0]]),maxbg, np.max((sp_first-bg_first)[q1[0]])])
	    plt.ylim(np.max([ -20, np.min((sp_first-bg_first)[q1[0]])]), np.min([topcnt, maxcounts]))
         if optimal_extraction:
	    p5, = plt.plot(x[q1[0]],counts[1,q1[0]],'g',alpha=0.5,ls='steps',lw=1.2,label='optimal' )
	    p6, = plt.plot(x[q1[0]],counts[1,q1[0]],'k',alpha=0.5,ls='steps',lw=1.2,label='_nolegend_' )
	    p7, = plt.plot(x[q1[0]], bg_first[q1[0]],'y',alpha=0.7,lw=1.1,ls='steps',label='background') 	    
	    plt.legend([p3,p5,p7],['spectrum','optimal','background'],loc=0,)
	    topcnt = 1.2 * np.max((sp_first-bg_first)[q1[0]])	    
	    ylim1,ylim2 = -10,  np.min([topcnt, maxcounts])
	    plt.ylim( ylim1,  ylim2 )
	    
	 #plt.xlim(ank_c[2]-ank_c[1],ank_c[3]-ank_c[1])
	 plt.xlim(xlim1,xlim2)
	 plt.ylabel('1st order counts')
	 
	 # plot second order 
	 ax23 = plt.subplot(nsubplots,1,3) 
	 plt.rcParams['legend.fontsize'] = 'small'
         #plt.xlim(ank_c[2],ank_c[3])
	 if fit_second:
	    if curved != 'straight':
	       p1, = plt.plot(x[q2[0]],(sp_second-bg_second)[q2[0]],'r',label='spectrum') 	    
	       plt.plot(x[q2[0]],(sp_second-bg_second)[q2[0]],'k',alpha=0.2,label='_nolegend_') 	    
	       p7, = plt.plot(x[q2[0]],(bg_second)[q2[0]],'y',alpha=0.7,lw=1.1,label='background') 	    
	       qbad = np.where(quality[q2[0]] > 0)
	       p2, = plt.plot(x[qbad],(sp_second-bg_second)[qbad],'+k',alpha=0.3,label='suspect')
	       plt.legend((p1,p7,p2),('spectrum','background','suspect'),loc=2)
	       plt.ylim(np.max([ -100, np.min((sp_second-bg_second)[q2[0]])]), \
	          np.min([np.max((sp_second-bg_second)[q2[0]]), maxcounts]))
            plt.xlim(ank_c[2]-ank_c[1],ank_c[3]-ank_c[1])
            if optimal_extraction:
	       p3, = plt.plot(x[q2[0]],counts[2,q2[0]],'g',alpha=0.5,ls='steps',label='optimal' )
	       plt.legend((p1,p7,p2,p3),('spectrum','background','suspect','optimal',),loc=2)
	       #plt.ylim(np.max([ -10,np.min(counts[2,q2[0]]), np.min((sp_second-bg_second)[q2[0]])]),\
	       #   np.min([np.max(counts[2,q2[0]]), np.max((sp_second-bg_second)[q2[0]]), maxcounts]))
	       plt.ylim( ylim1,ylim2 )
	 if predict2nd :
	       p4, = plt.plot(dis2p+dist12,flux2p, ls='steps',label='predicted')
	       p5, = plt.plot(dis2p[np.where(qual2p != 0)]+dist12,flux2p[np.where(qual2p != 0)],'+k',label='suspect',markersize=4)         
	       if optimal_extraction & fit_second:
	          plt.legend((p1,p2,p3,p4,p5),('curved','suspect','optimal','predicted','suspect'),loc=2)
	          #plt.ylim(np.max([ -100,np.min(counts[2,q2[0]]), np.min((sp_second-bg_second)[q2[0]])]),\
		  #   np.min([np.max(counts[2,q2[0]]), np.max((sp_second-bg_second)[q2[0]]), maxcounts]))
	          plt.ylim( ylim1,ylim2 )
	       elif optimal_extraction:
	          plt.legend((p1,p7,p4,p5),('curved','background','predicted','suspect'),loc=2)
	          plt.ylim(np.max([ -10, np.min((sp_second-bg_second)[q2[0]])]), \
		     np.min([np.max((sp_second-bg_second)[q2[0]]), maxcounts]))	
	       elif fit_second:
	          plt.legend((p1,p2,p4,p5),('curved','suspect','predicted','suspect'),loc=2)
	          plt.ylim(np.max([ -10, np.min((sp_second-bg_second)[q2[0]])]), \
		     np.min([np.max((sp_second-bg_second)[q2[0]]), maxcounts]))	
	       else:
	          plt.legend((p4,p5),('predicted','suspect'),loc=2)
	          plt.ylim(np.max([ -10, np.min((sp_second-bg_second)[q2[0]])]), \
		     np.min([np.max((sp_second-bg_second)[q2[0]]), maxcounts]))	
                  plt.xlim(ank_c[2]-ank_c[1],ank_c[3]-ank_c[1])
	                      
	 plt.xlim(xlim1,xlim2)
	 plt.ylabel('2nd order counts')      
	 
	 if fit_second:	 
	    ax24 = plt.subplot(nsubplots,1,4) 
	    plt.rcParams['legend.fontsize'] = 'small'
	    if (len(q3[0]) > 1) & (curved != "xxx"):
	       p1, = plt.plot(x[q3[0]],(sp_third-bg_third)[q3[0]],'r',label='spectrum') 	    
	       plt.plot(x[q3[0]],(sp_third-bg_third)[q3[0]],'k',alpha=0.2,label='_nolegend_') 	    
	       qbad = np.where(quality[q3[0]] > 0)
	       p2, = plt.plot(x[qbad],(sp_third-bg_third)[qbad],'xk',alpha=0.3,label='suspect')
	       p3, = plt.plot(x[q3[0]],bg_third[q3[0]],'y',label='background') 	    
	       plt.legend([p1,p3,p2],['spectrum','background','suspect'],loc=2)
	       plt.ylim(np.max([ -100, np.min((sp_second-bg_second)[q3[0]])]),\
	          np.min([np.max((sp_third-bg_third)[q3[0]]), maxcounts]))
            if optimal_extraction:
	       p4, = plt.plot(x[q3[0]],counts[3,q3[0]],'b',alpha=0.5,ls='steps',label='optimal' )
	       plt.legend([p1,p3,p2,p4],['spectrum','background','suspect','optimal',],loc=2)
	       #plt.ylim(np.max([ -100,np.min(counts[3,q3[0]]), np.min((sp_second-bg_second)[q3[0]])]),\
	       #   np.min([np.max(counts[3,q3[0]]), np.max((sp_third-bg_third)[q3[0]]), maxcounts]))
	       plt.ylim( ylim1,ylim2 )
            #plt.xlim(ank_c[2]-ank_c[1],ank_c[3]-ank_c[1])
	    plt.xlim(xlim1,xlim2)
	    plt.ylabel(u'3rd order counts')
	    plt.xlabel(u'pixel distance from anchor position')


      if (plot_spec):
         plt.winter()
      #  NEED the flux cal applied!
         nsubplots = 2
	 if not fit_second: 
	    nsubplots = 1
         fig3 = plt.figure(3)
	 plt.clf()
         wav1 = polyval(C_1,x[q1[0]])
	 ax31 = plt.subplot(nsubplots,1,1) 
	 if curved != "xxx":
	    rate1 = ((sp_first[q1[0]]* apercorr[1,[q1[0]]]-bg_first[q1[0]] ) 
	            /expospec[1,[q1[0]]]).flatten()
	    #bkgrate1 = ((bg_first)[q1[0]] * apercorr[1,[q1[0]]] 
	    #       /expospec[1,[q1[0]]]).flatten()
	    bkgrate1 = ((bg_first)[q1[0]] 
	            /expospec[1,[q1[0]]]).flatten()
            flux1 = rate2flux(wav1,rate1, wheelpos, bkgrate=bkgrate1, 
	                pixno=x[q1[0]], sig1coef=sig1coef, 
			sigma1_limits=[2.6,4.0], 
			arf1=fluxcalfile, arf2=None, 
			spectralorder=1, swifttime=tstart, 
			trackwidth = trackwidth, anker=anker, 
			option=2, fudgespec=1.0,
			frametime=framtime, 
	                debug=False,chatter=1)
            #flux1_err = rate2flux(wave,rate_err, wheelpos, spectralorder=1,)
	    p1, = plt.plot(wav1[np.isfinite(flux1)],flux1[np.isfinite(flux1)],
	                   color='darkred',label=u'curved') 	    
	    	    
	    #  PROBLEM quality flags !!!
	    qbad1 = np.where((quality[x[q1[0]]] > 0) & (quality[x[q1[0]]] < 16))
	    plt.legend([p1],[u'curved'])
	    if len(qbad1[0]) > 0:      
               p2, = plt.plot(wav1[qbad1],flux1[qbad1],
	             '+k',markersize=4,label=u'suspect')
	       plt.legend([p1,p2],[u'curved',u'suspect'])
	    plt.ylabel(u'1st order flux $(erg\ cm^{-2} s^{-1} \AA^{-1)}$')
	    # find reasonable limits flux 
	    qf = np.max(flux1[int(len(wav1)*0.3):int(len(wav1)*0.7)])
	    if qf > 2e-12: qf = 2e-12
	    plt.ylim(0.001*qf,1.2*qf)
	    plt.xlim(1600,6000)

	 if optimal_extraction:   # no longer supported (2013-04-24)
	    print "OPTIMAL EXTRACTION IS NO LONGER SUPPORTED"
	    wav1 = np.polyval(C_1,x[q1[0]])
	    #flux1 = rate2flux(wav1, counts[1,q1[0]]/expo, wheelpos, spectralorder=1, arf1=fluxcalfile)
            flux1 = rate2flux(wav1,counts[1,q1[0]]/expo, wheelpos, bkgrate=bgkrate1, pixno=x[q1[0]], sig1coef=sig1coef, \
	       sigma1_limits=[2.6,4.0], arf1=fluxcalfile, arf2=None, spectralorder=1, swifttime=tstart,\
	       trackwidth = trackwidth, anker=anker, option=2, fudgespec=1.0,frametime=framtime, \
	       debug=False,chatter=1)
	    p3, = plt.plot(wav1, flux1,'g',alpha=0.5,ls='steps',lw=2,label='optimal' )
	    p4, = plt.plot(wav1,flux1,'k',alpha=0.5,ls='steps',lw=2,label='_nolegend_' )
	    plt.legend([p1,p2,p3],['curved','suspect','optimal'],loc=0,)

	    qf = (flux1 > 0.) & (flux1 < 1.0e-11)
	    plt.ylim( -0.01*np.max(flux1[qf]),  1.2*np.max(flux1[qf]) )
	    plt.ylabel(u'1st order count rate')
         plt.xlim(np.min(wav1)-10,np.max(wav1))
	 plt.title(obsid+'+'+str(ext))
	 
	 if fit_second:
            ax32 = plt.subplot(nsubplots,1,2) 
	    plt.plot([1650,3200],[0,1])
	    plt.text(2000,0.4,'NO SECOND ORDER DATA',fontsize=16)	 	    
	    if curved != 'xxx':
	       wav2 = polyval(C_2,x[q2[0]]-dist12)
	       rate2 = ((sp_second[q2[0]]* apercorr[2,[q2[0]]]-bg_second[q2[0]]) /expospec[2,[q2[0]]]).flatten()
               flux2 = rate2flux(wav2, rate2, wheelpos, spectralorder=2,swifttime=tstart)
               #flux1_err = rate2flux(wave,rate_err, wheelpos, spectralorder=1,)
	       plt.cla()
	       p1, = plt.plot(wav2,flux2,'r',label='curved') 	    
	       plt.plot(wav2,flux2,'k',alpha=0.2,label='_nolegend_') 	    
	       qbad = np.where((quality > 0) & (quality < 32))
	       qbad1 = np.where((quality[x[q2[0]]] > 0) & (quality[x[q2[0]]] < 16))
	       p2, = plt.plot(wav2[qbad1],flux2[qbad1],'+k',markersize=4,label='suspect')
	       plt.legend(['curved','suspect'])
	       plt.ylabel(u'2nd order flux $(erg\ cm^{-2} s^{-1} \AA^{-1)}$')
            plt.xlim(1600,3200)

	    qf = (flux1 > 0.) & (flux1 < 1.0e-11)
	    if np.sum(qf[0]) > 0:
               plt.ylim( -0.01*np.max(flux1[qf]),  1.2*np.max(flux1[qf]) )
	    else: plt.ylim(1e-16,2e-12)  
	 # final fix to limits of fig 3,1   
	 y31a,y31b = ax31.get_ylim()
	 setylim = False
	 if y31a < 1e-16: 
	    y31a = 1e-16
	    setylim = True
	 if y31b > 1e-12:
	    y31b = 1e-12
	    setylim = True
	 if setylim: ax31.set_ylim(bottom=y31a,top=y31b)           
         #
	 plt.xlabel(u'$\lambda(\AA)$',fontsize=16)
      
      
   # output parameter 
   Y1 = ( (dis,spnet,angle,anker,anker2,anker_field,ank_c), (bg,bg1,bg2,extimg,spimg,spnetimg,offset), 
           (C_1,C_2,img),  hdr,m1,m2,aa,wav1 )	 
	     
   # output parameter 
   Y2 = fit, (coef0,coef1,coef2,coef3), (bg_zeroth,bg_first,bg_second,bg_third), (borderup,borderdown), apercorr, expospec	
	       
   # writing output to a file 
   #try:
   if wr_outfile:      # write output file
    
      if ((chatter > 0) & (not clobber)): print "trying to write output files"
      import uvotio
      
      if (curved == 'straight') & (not optimal_extraction): 
         ank_c2 = np.copy(ank_c) ; ank_c2[1] -= m1
         F = uvotio.wr_spec(RA,DEC,filestub,ext,hdr,anker,anker_field[0],anker_field[1],dis[aa],wav1  \
                 ,spnet[aa]/expo,bg[aa]/expo,bg1[aa]/expo,bg2[aa]/expo,offset,ank_c2,extimg, C_1, \
                  history=None,chatter=1,clobber=clobber, interactive=interactive)  
		  
      elif not optimal_extraction:
         Y = (Y0,Y1,Y2,Y4)
         F = uvotio.writeSpectrum(RA,DEC,filestub,ext, Y,  
	      fileoutstub=outfile, 
	      arf1=fluxcalfile, arf2=None, 
	      fit_second=fit_second, 
	      write_rmffile=write_RMF,
	      used_lenticular=use_lenticular_image,
	      history=msg, 
	      chatter=chatter, 
	      clobber=clobber ) 
	  
	    
      elif optimal_extraction:
         Y = (Y0,Y1,Y2,Y3,Y4)
         F = uvotio.OldwriteSpectrum(RA,DEC,filestub,ext, Y, mode=2, 
	    quality=quality, interactive=False,fileout=outfile,
	    updateRMF=write_rmffile, \
	    history=msg, chatter=5, clobber=clobber)
      		  
   #except (RuntimeError, IOError, ValueError):
   #   print "ERROR writing output files. Try to call uvotio.wr_spec."  
   #   pass
       
   # clean up fake file 
   if tempntags.__contains__('fakefilestub'):
         filestub = tempnames[tempntags.index('fakefilestub')]
         os.system('rm '+filestub+'ufk_??.img ')

   # update Figure 3 to use the flux...
   
   # TBD
       
   # write the summary 
       
   sys.stdout.write(msg)
   sys.stdout.write(msg2)
   
   flog = open(logfile,'a')
   flog.write(msg)
   flog.write(msg2)
   flog.close()
       
   if give_result: return Y0, Y1, Y2, Y3, Y4   



def extractSpecImg(file,ext,anker,angle,anker0=None,anker2=None, anker3=None,\
        searchwidth=35,spwid=13,offsetlimit=None, fixoffset=None, 
	background_lower=[None,None], background_upper=[None,None],
	clobber=True,chatter=2):
   '''
   extract the grism image of spectral orders plus background
   using the reference point at 2600A in first order.
   
   Parameters
   ----------
   file : str
     input file location     
   ext  : int
     extension of image
   anker : list, ndarray
      X,Y coordinates of the 2600A (1) point on the image in image coordinates
   angle : float
      angle of the spectrum at 2600A in first order from zemax    e.g., 28.8  
   searchwidth : float
      find spectrum with this possible offset ( in crowded fields
      it should be set to a smaller value)	 
   
   use_rectext : bool
      If True then the HEADAS uvotimgrism program rectext is used to extract the image 
      This is a better way than using ndimage.rotate() which does some weird smoothing.
   
   History
   -------
   2011-09-05 NPMK changed interpolation in rotate to linear, added a mask image to 
   make sure to keep track of the new pixel area.  	     
   2011-09-08 NPMK incorporated rectext as new extraction and removed interactive plot, 
     curved, and optimize which are now olsewhere.
   ''' 
   import numpy as np
   import os
   import pyfits
   import scipy.ndimage as ndimage
   
   #out_of_img_val = -1.0123456789 now a global 

   if chatter > 4:
      print 'extractSpecImg parameters: file, ext, anker, angle'
      print file,ext
      print anker,angle
      print 'searchwidth,chatter,spwid,offsetlimit, :'
      print searchwidth,chatter,spwid,offsetlimit

   img, hdr = pyfits.getdata(file,ext,header=True)
   img = np.array(img)
   wheelpos = hdr['WHEELPOS']

   if chatter > 4: print 'wheelpos:', wheelpos

   if not use_rectext:
      # now we want to extend the image array and place the anchor at the centre
      s1 = 0.5*img.shape[0]
      s2 = 0.5*img.shape[1]

      d1 = -(s1 - anker[1])   # distance of anker to centre img 
      d2 = -(s2 - anker[0])
      n1 = 2.*abs(d1) + img.shape[0] + 400  # extend img with 2.x the distance of anchor 
      n2 = 2.*abs(d2) + img.shape[1] + 400

      #return img, hdr, s1, s2, d1, d2, n1, n2
      if 2*int(n1/2) == int(n1): n1 = n1 + 1
      if 2*int(n2/2) == int(n2): n2 = n2 + 1
      c1 = n1 / 2 - anker[1] 
      c2 = n2 / 2 - anker[0]
      if chatter > 3: print 'array info : ',img.shape,d1,d2,n1,n2,c1,c2
   
      # the ankor is now centered in array a; initialize a with out_of_img_val
      a = np.zeros( (n1,n2), dtype=float) + cval
      # load array in middle
      a[c1:c1+img.shape[0],c2:c2+img.shape[1]] = img
      # patch outer regions with something like mean to get rid of artifacts
      mask = abs(a - cval) < 1.e-8
      # Kludge:
      # test image for bad data and make a fix by putting the image average in its place
      aanan = np.isnan(a)
      aagood = np.isfinite(a)
      aaave = a[np.where(aagood)].mean()
      a[np.where(aanan)] = aaave
      if len( np.where(aanan)[0]) > 0 :
         print "extractSpecImg WARNING: BAD IMAGE DATA fixed by setting to mean of good data whole image " 
   
   # now we want to rotate the array to have the dispersion in the x-direction 
   if angle < 40. : 
      theta = 180.0 - angle
   else: theta = angle      
   
   if not use_rectext:
      b = ndimage.rotate(a,theta,reshape = False,order = 1,mode = 'constant',cval = cval)
      e2 = 0.5*b.shape[0]
      c = b[e2-100:e2+100,:]
      ank_c = [ (c.shape[0]-1)/2+1, (c.shape[1]-1)/2+1 , 0, c.shape[1]]
      
   if use_rectext:
      # build the command for extracting the image with rectext   
      outfile= tempnames[tempntags.index('rectext')]
      cosangle = np.cos(theta/180.*np.pi)
      sinangle = np.sin(theta/180.*np.pi)
      # distance anchor to pivot 
      dx_ank = - (hdr['naxis1']-anker[0])/cosangle + 100.0*sinangle 
      if np.abs(dx_ank) > 760: dx_ank = 760   # include zeroth order (375 for just first order)
      # distance to end spectrum
      dx_2   =                -anker[0] /cosangle + 100.0/sinangle  # to lhs edge
      dy_2   =  (hdr['naxis2']-anker[1])/sinangle - 100.0/cosangle  # to top edge
      dx = int(dx_ank + np.array([dx_2,dy_2]).min() )   # length rotated spectrum 
      dy = 200 # width rotated spectrum
      # pivot x0,y0
      x0 = anker[0] - dx_ank*cosangle  + dy/2.*sinangle
      y0 = anker[1] - dx_ank*sinangle  - dy/2.*cosangle

      command= "rectext infile="+file+"+"+str(ext)
      command+=" outfile="+outfile
      command+=" angle="+str(theta)+" width="+str(dx)
      command+=" height="+str(dy)+" x0="+str(x0)+" y0="+str(y0)
      command+=" null="+str(cval)
      command+=" chatter=5 clobber=yes"
      print command
      os.system(command)
      c = extimg = pyfits.getdata(outfile,0)
      ank_c = np.array([100,dx_ank,0,extimg.shape[1]])
      # out_of_img_val = 0.
      if clobber:
         os.system("rm "+outfile)
       
   # extract the strips with the background on both sides, and the spectral orders
   # find optimised place of the spectrum
   
   # first find parts not off the detector 
   eps1 = 1e-15 # remainder after resampling for intel-MAC OSX system (could be jacked up)
   qofd = np.where( abs(c[100,:] - cval) > eps1 )
   if wheelpos < 300:   # UV grism
      disrange = 150    # perhaps make parameter in call?
      disscale = 10     # ditto
      minrange = disrange/10 # 300 is maximum
      maxrange = np.array([disrange*10,c.shape[1]-ank_c[1]-2]).min()  # 1200 is most of the spectrum 
   else:                # V grism
      disrange = 120    # perhaps make parameter in call?
      disscale = 6      # ditto
      minrange = np.array([disrange/2,ank_c[1]-qofd[0].min() ]).max() # 300 is maximum
      maxrange = np.array([disrange*5,c.shape[1]-ank_c[1]-2],qofd[0].max()-ank_c[1]).min()  # 600 is most of the spectrum   
        
   if chatter > 1: 
      #print 'image was rotated; anchor in extracted image is ', ank_c[:2]
      #print 'limits spectrum are ',ank_c[2:]
      print 'finding location spectrum from a slice around anchor sized:',minrange,':',maxrange
      print 'offsetlimit = ', offsetlimit  
   d = (c[:,(ank_c[1]-minrange):(ank_c[1]+maxrange)]).sum(axis=1).squeeze()
   if len(qofd[0]) > 0:
     ank_c[2] = min(qofd[0])
     ank_c[3] = max(qofd[0])
   else: 
     ank_c[2] = -1
     ank_c[3] = -1 

   if fixoffset == None:
      offset = ( (np.where(d == (d[100-searchwidth:100+searchwidth]).max() ) )[0] - 100 )
      if chatter>0: print 'offset found is : ', -offset
      if len(offset) == 0:
         print 'offset problem: offset set to zero'
         offset = 0
      offset = offset[0]
      if offsetlimit != None:
        if abs(offset) >= offsetlimit: 
           offset = 0 
	   print 'This is larger than the offsetlimit. The offset has been set to 0'
	   if interactive: 
	      offset = float(raw_input('Please give a value for the offset:  '))
   else: offset = fixoffset	      
   if chatter>0: 
      print 'offset used is : ', -offset	 
      
   ank_c[0] += offset  
 
   print 'image was rotated; anchor in extracted image is [', ank_c[0],',',ank_c[1],']'
   print 'limits spectrum on image in dispersion direction are ',ank_c[2],' - ',ank_c[3] 
   
   # Straight extraction :
   sphalfwid = int(spwid-0.5)/2
   splim1 = 100+offset-sphalfwid+1
   splim2 = splim1 + spwid
   spimg  = c[splim1:splim2,:]
	 
   if chatter > 0: 
      print 'Extraction limits across dispersion: splim1,splim2 = ',splim1,' - ',splim2
      
   bg, bg1, bg2, bgsigma, bgimg, bg_limits, bgextras = findBackground(c, 
       background_lower=background_lower, background_upper=background_upper,yloc_spectrum=ank_c[0] )
       
   bgmean = bg
   bg = 0.5*(bg1+bg2)
   if chatter > 0: print 'Background : ', bgmean,' +/- ',bgsigma,' (1-sigma error)' 
   # define the dispersion with origen at the projected position of the 
   # 2600 point in first order
   dis = np.arange((c.shape[1]),dtype=np.int16) - ank_c[1] 

   # remove the background  
   #bgimg_ = 0.* spimg.copy()
   #for i in range(bgimg_.shape[0]): bgimg_[i,:]=bg
   spnetimg = spimg - bg
   spnet = spnetimg.sum(axis=0)
   return dis, spnet, bg, bg1, (bg2, bgsigma, bgimg, bg_limits, bgextras), c, spimg, spnetimg, offset, ank_c   
   
   
def findBackground(extimg,background_lower=[None,None], background_upper=[None,None],yloc_spectrum=100, 
    smo1=None, smo2=None, chatter=2):
   '''Extract the background from the image slice containing the spectrum.
   
   Parameters
   ----------
   extimg : 2D array
      image containing spectrum. Dispersion approximately along x-axis.
   background_lower : list
      distance in pixels from `yloc_spectrum` of the limits of the lower background region.
   background_upper : list
      distance in pixels from `yloc_spectrum` of the limits of the upper background region.   
   yloc_spectrum : int
      pixel `Y` location of spectrum
   smo1 : float
      smoothing parameter passed to smoothing spline fitting routine. `None` for default.  
   smo2 : float
      smoothing parameter passed to smoothing spline fitting routine. `None` for default. 
   chatter : int
      verbosity
      
   Returns
   -------
   bg : float
      mean background 
   bg1, bg2 : 1D arrays
      bg1 = lower background; bg2 = upper background
   bgsig : float
      standard deviation of background  
   bgimg : 2D array
      image of the background constructed from bg1 and/or bg2   
   bg_limits_used : list, length 4
      limits used for the background in the following order: lower background, upper background    
   (bg1_good, bg1_dis, bg1_dis_good, bg2_good, bg2_dis, bg2_dis_good, bgimg_lin) : tuple
      various other background measures    
   
   Notes
   -----
   
   **Global parameter**
   
     - **background_method** : {'boxcar','splinefit'}

   The two background images can be computed 2 ways:
   
     1. 'splinefit': sigma clip image, then fit a smoothing spline to each row, then average in y for each background region
     2. 'boxcar':   select the background from the smoothed image created by method 1 below.
     
   extimg  is the image containing the spectrum in the 1-axis centered in 0-axis
   `ank` is the position of the anchor in the image 
      
   I create two background images:
    
         1. split the image strip into 40 portions in x, so that the background variation is small
	    compute the mean 
	    sigma clip (3 sigma) each area to to the local mean
	    replace out-of-image pixels with mean of whole image (2-sigma clipped)
	    smooth with a boxcar by the smoothing factor
	 2. compute the background in two regions upper and lower 
	    linearly interpolate in Y between the two regions to create a background image   
      
      bg1 = lower background; bg2 = upper background
      
      smo1, smo2 allow one to relax the smoothing factor in computing the smoothing spline fit
      
   History
   -------
   -  8 Nov 2011 NPM Kuin complete overhaul	
          things to do: get quality flagging of bad background points, edges perhaps done here?    
   -  13 Aug 2012: possible problem was seen of very bright sources not getting masked out properly 
          and causing an error in the background that extends over a large distance due to the smoothing.
	  The cause is that the sources are more extended than can be handled by this method. 
	  A solution would be to derive a global background 	      		 
      '''
   import numpy as np   
   try:
     from convolve import boxcar
   except:
     from stsci.convolve import boxcar
     
   # initialize parameters
   
   bgimg    = extimg.copy()
   out    = np.where( (np.abs(bgimg-cval) <= 1e-6) )
   in_img = np.where( (np.abs(bgimg-cval) >  1e-6) & np.isfinite(bgimg) )
   nx = bgimg.shape[1]  # number of points in direction of dispersion
   ny = bgimg.shape[0]  # width of the image
   kx0 = 0 ; kx1 = nx # default limits for valid lower background  
   kx2 = 0 ; kx3 = nx # default limits for valid upper background  
   ny4 = int(0.25*ny) # default width of each default background region 
   
   sig1 = 1 # unit for background offset, width
   bg_limits_used = [0,0,0,0]  # return values used 

   # here we replace the > 2.5 sigma peaks with the mean  
   # after subdividing the image strip to allow for the 
   # change in background level which can be > 2 over the 
   # image. Off-image parts are set to image mean. 
      
   xlist = np.linspace(0,bgimg.shape[1],80)
   xlist = np.asarray(xlist,dtype=int)
   imgstats = imagestats.ImageStats(bgimg[in_img[0],in_img[1]],nclip=3)   
   bg = imgstats.mean
   bgsig  = imgstats.stddev
   if chatter > 1:
      print 'background statistics: mean , sigma : ',bg, bgsig
      
   # create boolean image flagging good pixels
   img_good = np.ones(extimg.shape,dtype=bool)
   # flag area out of picture as bad
   img_good[out] = False
   
   # replace high values in image with estimate of mean  and flag them as not good   
   
   for i in range(78):
      sub_bg = boxcar(bgimg[:,xlist[i]:xlist[i+2]] , (5,5), mode='reflect', cval=cval)
      sub_bg_use = np.where( np.abs(sub_bg - cval) > 1.0e-5 ) # list of coordinates
      imgstats = None
      if sub_bg_use[0].size > 0: 
         imgstats = imagestats.ImageStats(sub_bg[sub_bg_use],nclip=3)
	 # patch values in image (not out of image) with mean if outliers
	 aval = 2.0*imgstats.stddev
         img_clip_ = (np.abs(bgimg[:,xlist[i]:xlist[i+2]]-cval) < 1e-6) | (np.abs(sub_bg - imgstats.mean) > aval) | (sub_bg <= 0.) | np.isnan(sub_bg)
	 bgimg[:,xlist[i]:xlist[i+2]][img_clip_] = imgstats.mean  # patch image
	 img_good[:,xlist[i]:xlist[i+2]][img_clip_] = False       # flag patches 

   if chatter > 1: 
      if background_method == 'boxcar': 
         print "BACKGROUND METHOD:",background_method, "background smoothing =",background_smoothing
      else:
         print "BACKGROUND METHOD:",background_method 
      
   if not ((background_method == 'splinefit') | (background_method == 'boxcar') ):
      print 'background method missing; currently reads : ',background_method

   if background_method == 'boxcar':	    
      # boxcar smooth in x,y using the global parameter background_smoothing
      bgimg = boxcar(bgimg,background_smoothing,mode='reflect',cval=cval)
   
   if background_lower[0] == None:
      bg1 = bgimg[0:ny4,:].copy()
      bg_limits_used[0]=0
      bg_limits_used[1]=ny4
      bg1_good = img_good[0:ny4,:] 
      kx0 = np.min(np.where(img_good[0,:]))+10  # assuming the spectrum is in the top two thirds of the detector
      kx1 = np.max(np.where(img_good[0,:]))-10
   else:
      # no curvature, no second order:  limits 
      bg1_1= np.max(np.array([yloc_spectrum - sig1*background_lower[0],20 ]))
      #bg1_0=  np.max(np.array([yloc_spectrum - sig1*(background_lower[0]+background_lower[1]),0]))
      bg1_0=  np.max(np.array([yloc_spectrum - sig1*(background_lower[1]),0]))
      bg1 = bgimg[bg1_0:bg1_1,:].copy() 
      bg_limits_used[0]=bg1_0
      bg_limits_used[1]=bg1_1
      bg1_good = img_good[bg1_0:bg1_1,:] 
      kx0 = np.min(np.where(img_good[bg1_0,:]))+10  # assuming the spectrum is in the top two thirds of the detector   
      kx1 = np.max(np.where(img_good[bg1_0,:]))-10  # corrected for edge effects
      
   #if ((kx2-kx0) < 20): 
   #   print 'not enough valid upper background points'   

   if background_upper[0] == None:
      bg2 = bgimg[-ny4:ny,:].copy()
      bg_limits_used[2]=ny-ny4
      bg_limits_used[3]=ny
      bg2_good = img_good[-ny4:ny,:]
      kx2 = np.min(np.where(img_good[ny-1,:]))+10  # assuming the spectrum is in the top two thirds of the detector
      kx3 = np.max(np.where(img_good[ny-1,:]))-10
   else:   
      bg2_0= np.min(np.array([yloc_spectrum + sig1*background_upper[0],180 ]))
      #bg2_1=  np.min(np.array([yloc_spectrum + sig1*(background_upper[0]+background_upper[1]),ny]))
      bg2_1=  np.min(np.array([yloc_spectrum + sig1*(background_upper[1]),ny]))
      bg2 = bgimg[bg2_0:bg2_1,:].copy()
      bg_limits_used[2]=bg2_0
      bg_limits_used[3]=bg2_1
      bg2_good = img_good[bg2_0:bg2_1,:]
      kx2 = np.min(np.where(img_good[bg2_1,:]))+10  # assuming the spectrum is in the top two thirds of the detector
      kx3 = np.max(np.where(img_good[bg2_1,:]))-10
      
   #if ((kx3-kx2) < 20): 
   #   print 'not enough valid upper background points'   
      

   if background_method == 'boxcar': 
      bg1 = bg1_dis = bg1.mean(0)
      bg2 = bg2_dis = bg2.mean(0)
      bg1_dis_good = np.zeros(nx,dtype=bool)
      bg2_dis_good = np.zeros(nx,dtype=bool)
      for i in range(nx):
        bg1_dis_good[i] = np.where(bool(int(bg1_good[:,i].mean(0))))
        bg2_dis_good[i] = np.where(bool(int(bg2_good[:,i].mean(0))))
      
   if background_method == 'splinefit':	 
   
      #  mean bg1_dis, bg2_dis across dispersion 
      
      bg1_dis = np.zeros(nx) ; bg2_dis = np.zeros(nx)
      for i in range(nx):
         bg1_dis[i] = bg1[:,i][bg1_good[:,i]].mean()
         if not bool(int(bg1_good[:,i].mean())): 
	    bg1_dis[i] = cval	   
         bg2_dis[i] = bg2[:,i][bg2_good[:,i]].mean()  
         if not bool(int(bg2_good[:,i].mean())): 
	    bg2_dis[i] = cval
      
      # some parts of the background may have been masked out completely, so 
      # find the good points and the bad points   
      bg1_dis_good = np.where( np.isfinite(bg1_dis) & (np.abs(bg1_dis - cval) > 1.e-7) )
      bg2_dis_good = np.where( np.isfinite(bg2_dis) & (np.abs(bg2_dis - cval) > 1.e-7) )
      bg1_dis_bad = np.where( ~(np.isfinite(bg1_dis) & (np.abs(bg1_dis - cval) > 1.e-7)) )   
      bg2_dis_bad = np.where( ~(np.isfinite(bg2_dis) & (np.abs(bg2_dis - cval) > 1.e-7)) )
      	         
      # fit a smoothing spline to each background 
         
      x = bg1_dis_good[0]
      s = len(x) - np.sqrt(2.*len(x)) 
      if smo1 != None: s = smo1
      if len(x) > 40: x = x[7:len(x)-7]  # clip end of spectrum where there is downturn
      w = np.ones(len(x))   
      tck1 = interpolate.splrep(x,bg1_dis[x],w=w,xb=bg1_dis_good[0][0],xe=bg1_dis_good[0][-1],k=3,s=s) 
      bg1 = np.ones(nx) *  (bg1_dis[x]).mean()  
      bg1[np.arange(kx0,kx1)] = interpolate.splev(np.arange(kx0,kx1), tck1)
   
      x = bg2_dis_good[0]
      s = len(x) - np.sqrt(2.*len(x))      
      if smo2 != None: s = smo1
      if len(x) > 40: x = x[10:len(x)-10]  # clip
      w = np.ones(len(x))   
      tck2 = interpolate.splrep(x,bg2_dis[x],w=w,xb=bg2_dis_good[0][0],xe=bg2_dis_good[0][-1],k=3,s=s)    
      bg2 = np.ones(nx) *  (bg2_dis[x]).mean()  
      bg2[np.arange(kx2,kx3)] = interpolate.splev(np.arange(kx2,kx3), tck2)
      
      # force bg >= 0:
      # spline can do weird things ?
      negvals = bg1 < 0.0
      if negvals.any(): 
         bg1[negvals] = 0.0
	 if chatter > 1:
  	    print "background 1 set to zero in ",len(np.where(negvals)[0])," points"
      
      negvals = bg2 < 0.0
      if negvals.any(): 
         bg2[negvals] = 0.0
	 if chatter > 1:
	    print "background 1 set to zero in ",len(np.where(negvals)[0])," points"
   
   # image constructed from linear inter/extra-polation of bg1 and bg2
   
   bgimg_lin = np.zeros(ny*nx).reshape(ny,nx)
   dbgdy = (bg2-bg1)/(ny-1)
   for i in range(ny):
      bgimg_lin[i,:] = bg1 + dbgdy*i
      
   if background_method != '0123':   # always
     # interpolate background
     if ( (background_lower[0] == None) & (background_upper[0] == None)):
        # default background region
        dbgdy = (bg2-bg1)/150.0 # assuming height spectrum 200 and width extraction regions 30 pix each
        for i9 in range(bgimg.shape[0]):
           bgimg[i9,kx0:kx1] = bg1[kx0:kx1] + dbgdy[kx0:kx1]*(i9-25)
	   bgimg[i9,0:kx0] = bg2[0:kx0]
	   bgimg[i9,kx1:nx] = bg2[kx1:nx]
	print "1..BACKGROUND DEFAULT from BG1 and BG2"   
     elif ((background_lower[0] != None) & (background_upper[0] == None)):
     # set background to lower background region   
        for i9 in range(bgimg.shape[0]):
           bgimg[i9,:] = bg1 
	print "2..BACKGROUND from lower BG1 only"   
     elif ((background_upper[0] != None) & (background_lower[0] == None)):
     # set background to that of upper background region   
        for i9 in range(bgimg.shape[0]):
           bgimg[i9,:] = bg2
	print "3..BACKGROUND from upper BG2 only"   
     else:
     # linear interpolation of the two background regions  
        dbgdy = (bg2-bg1)/(background_upper[0]+0.5*background_upper[1]+background_lower[0]+0.5*background_lower[1]) 
        for i9 in range(bgimg.shape[0]):
           bgimg[i9,kx0:kx1] = bg1[kx0:kx1] + dbgdy[kx0:kx1]*(i9-int(100-(background_lower[0]+0.5*background_lower[1])))
	   bgimg[i9,0:kx0] =  bg2[0:kx0]    # assuming that the spectrum in not in the lower left corner 
	   bgimg[i9,kx1:nx] = bg2[kx1:nx]
	print "4..BACKGROUND from BG1 and BG2"   
      
   return bg, bg1, bg2, bgsig, bgimg, bg_limits_used, (bg1_good, bg1_dis, 
          bg1_dis_good, bg2_good, bg2_dis, bg2_dis_good, bgimg_lin)

      
def interpol(xx,x,y):
   ''' 
   linearly interpolate a function y(x) to return y(xx)
   no special treatment of boundaries
         
    2011-12-10 NPMKuin   skip all data points which are not finite
       '''
   import numpy as np    
     
   x = np.asarray(x.ravel())
   y = np.asarray(y.ravel())    
   q0 = np.isfinite(x) & np.isfinite(y)  # filter out NaN values 
   q1 = np.where(q0) 
   if len(q1[0]) == 0:
      print "error in arrays to be interpolated"
      print "x:",x
      print "y:",y
      print "arg:",xx
      
   x1 = x[q1[0]]
   y1 = y[q1[0]]
   q2 = np.where( np.isfinite(xx) )      # filter out NaN values
   kk = x1.searchsorted(xx[q2])-1
   # should extrapolate if element of k = len(a)
   #q = np.where(k == len(a)) ; k[q] = k[q]-1
   n = len(kk)
   f = np.zeros(n)
   f2 = np.zeros(len(xx))
   for i in range(n):
      k = kk[i]
      if k > (len(x1)-2):
         k = len(x1) - 2
      s = (y1[k+1]-y1[k])/(x1[k+1]-x1[k])
      f[i] = y1[k]+s*(xx[q2[0]][i]-x1[k]) 
   f2[q2] = f   
   f2[not q2] = np.NaN
   return f2      


def hydrogen(n,l):
  '''
  Return roughly the wavelength of the Hydrogen lines
  
  Lymann spectrum: l=0, n>l+1
  Balmer spectrum: l=1, n>2  
  Pachen spectrum: l=2, n>3                 
		   		   '''
  # Rydberg constant in m-1 units
  R = 1.097e7 
  inv_lam = R*(1./(l+1)**2 - 1./n**2)
  lam = 1./inv_lam * 1e10
  return lam


def boresight(filter='uvw1',order=1,wave=260,r2d=77.0,date=000,chatter=0):
   ''' These values should come out of the TELDEF file, but 
       the grism boresight positions of the grisms at 2600 in first order 
       have not been implemented therein. So I used this routine as a shortcut. 
       
       returns the boresight for a filter (in DET pixels)
       by adding (77,77) to the lenticular filter RAW coordinate.(see TELDEF file)
       the grism boresight was measured in DET (offset correction should be 104,78)

       Parameters
       ----------
       filter : str 
          one of {'ug200','uc160','vg1000','vc955',
	  'wh','v','b','u','uvw1','uvm2','uvw2'}
       
       Returns
       ------- 
       the boresight for a filter (in DET pixels)
       by adding (77,77) to the lenticular filter RAW coordinate.(see TELDEF file)
       the grism boresight was measured in DET 
       (The default r2d=77 returns the correct boresight for the grisms in 
       detector coordinates. To get the grism boresight in image coordinates, 
       subtract (104,78) typically.)
       	  
       NOTE: 
       -----
       THE TRANSLATION OF LENTICULAR IMAGE TO GRISM 
       IMAGE IS ALWAYS THE SAME, INDEPENDENT OF THE BORESIGHT.
       THEREFORE THE BORESIGHT DRIFT DOES NOT AFFECT THE 
       GRISM ANCHOR POSITIONS AS LONG AS THE DEFAULT 
       BORESIGHT POSITIONS ARE USED. [Becase those were used
       for the calibration].
       
   '''
   filterlist = 'ug200','uc160','vg1000','vc955','wh','v','b','u','uvw1','uvm2','uvw2'
       
   if date > 209952000:
      if chatter > 0: print 'date > 209952000'
      if   filter == 'uvw1': return 951.204+r2d, 1049.365+r2d
      elif filter == 'wh'  : return 949.902+r2d, 1048.837+r2d
      elif filter == 'v'   : return 951.741+r2d, 1049.890+r2d 
      elif filter == 'b'   : return 951.877+r2d, 1049.672+r2d 
      elif filter == 'u'   : return 956.984+r2d, 1047.841+r2d
      elif filter == 'uvm2': return 949.753+r2d, 1049.306+r2d 
      elif filter == 'uvw2': return 951.113+r2d, 1050.187+r2d
      elif filter == 'w1'  : return 951.204+r2d, 1049.365+r2d
      elif filter == 'm2'  : return 949.753+r2d, 1049.306+r2d 
      elif filter == 'w2'  : return 951.113+r2d, 1050.187+r2d
      elif filter == 'ug200':       
          if order == 1:
             if wave == 260: return 928.53+r2d,1002.69+r2d
          elif order == 0: return 1449.22+r2d, 707.7+r2d   
      elif filter == 'uc160':       
          if order == 1:
             if wave == 260: return 1025.1+r2d,945.3+r2d
          elif order == 0: return 1494.9+r2d, 605.8+r2d   
      elif filter == 'vg1000': 
          if order == 0: return 1506.8+r2d,664.3+r2d 
      elif filter == 'vc955':
          if order == 0: return 1542.5+r2d, 556.4+r2d
      else: 
          return filterlist
	  
   elif date > 179971200:
      if chatter > 0: print 'date > 179971200'
      if   filter == 'uvw1': return 953.496+r2d, 1047.929+r2d
      elif filter == 'wh'  : return 953.315+r2d, 1048.014+r2d
      elif filter == 'v'   : return 954.036+r2d, 1048.229+r2d 
      elif filter == 'b'   : return 953.795+r2d, 1048.180+r2d 
      elif filter == 'u'   : return 959.086+r2d, 1046.331+r2d
      elif filter == 'uvm2': return 952.024+r2d, 1048.025+r2d 
      elif filter == 'uvw2': return 953.675+r2d, 1048.962+r2d
      elif filter == 'w1'  : return 953.496+r2d, 1047.929+r2d
      elif filter == 'm2'  : return 952.024+r2d, 1048.025+r2d 
      elif filter == 'w2'  : return 953.675+r2d, 1048.962+r2d
      elif filter == 'ug200':       
          if order == 1:
             if wave == 260: return 928.53+r2d,1002.69+r2d
          elif order == 0: return 1449.22+2.4+r2d, 707.7-2.0+r2d   
      elif filter == 'uc160':       
          if order == 1:
             if wave == 260: return 1025.1+r2d,945.3+r2d
          elif order == 0: return 1501.4+2.4+r2d, 593.7-2.0+r2d   
      elif filter == 'vg1000': 
          if order == 0: return 1506.8+2.4+r2d,664.3-2.0+r2d 
      elif filter == 'vc955':
          if order == 0: return 1542.5+2.4+r2d, 556.4-2.0+r2d
      elif filter == 'list': 
          return filterlist
         
   elif date > 154483349:
      if chatter > 0: print 'date > 154483349'
      if   filter == 'uvw1': return 954.606+r2d, 1044.662+r2d
      elif filter == 'wh'  : return 954.506+r2d, 1043.486+r2d
      elif filter == 'v'   : return 955.064+r2d, 1045.976+r2d 
      elif filter == 'b'   : return 955.283+r2d, 1045.080+r2d 
      elif filter == 'u'   : return 960.064+r2d, 1043.327+r2d
      elif filter == 'uvm2': return 953.231+r2d, 1044.900+r2d 
      elif filter == 'uvw2': return 953.231+r2d, 1044.900+r2d
      elif filter == 'w1'  : return 954.606+r2d, 1044.662+r2d
      elif filter == 'm2'  : return 953.231+r2d, 1044.900+r2d
      elif filter == 'w2'  : return 953.231+r2d, 1044.900+r2d
      elif filter == 'ug200':       
          if order == 1:
             if wave == 260: return 928.53+r2d,1002.69+r2d
          elif order == 0: return 1449.22+3.4+r2d, 707.7-3.0+r2d   
      elif filter == 'uc160':       
          if order == 1:
             if wave == 260: return 1025.1+r2d,945.3+r2d
          elif order == 0: return 1501.4+3.4+r2d, 593.7-3.0+r2d   
      elif filter == 'vg1000': 
          if order == 0: return 1506.8+3.4+r2d,664.3-3.0+r2d 
      elif filter == 'vc955':
          if order == 0: return 1542.5+3.4+r2d, 556.4-3.0+r2d
      elif filter == 'list': 
          return filterlist
           
   elif date > 139968000:
      if chatter > 0: print 'date > 139968000'
      if   filter == 'uvw1': return 957.691+r2d, 1039.086+r2d
      elif filter == 'wh'  : return 956.000+r2d, 1039.775+r2d
      elif filter == 'v'   : return 957.390+r2d, 1042.647+r2d 
      elif filter == 'b'   : return 957.747+r2d, 1042.333+r2d 
      elif filter == 'u'   : return 961.675+r2d, 1041.594+r2d
      elif filter == 'uvm2': return 956.388+r2d, 1039.235+r2d
      elif filter == 'uvw2': return 957.717+r2d, 1040.371+r2d
      elif filter == 'w1'  : return 957.691+r2d, 1039.086+r2d
      elif filter == 'm2'  : return 956.388+r2d, 1039.235+r2d 
      elif filter == 'w2'  : return 957.717+r2d, 1040.371+r2d
      elif filter == 'ug200':       
          if order == 1:
             if wave == 260: return 928.53+r2d,1002.69+r2d
          elif order == 0: return 1449.22+6.4+r2d, 707.7-10+r2d   
      elif filter == 'uc160':       
          if order == 1:
             if wave == 260: return 1025.1+r2d,945.3+r2d
          elif order == 0: return 1501.4+6.4+r2d, 593.7-10+r2d   
      elif filter == 'vg1000': 
          if order == 0: return 1506.8+6.4+r2d,664.3-10+r2d 
      elif filter == 'vc955':
          if order == 0: return 1542.5+6.4+r2d, 556.4-10+r2d
      elif filter == 'list': 
          return filterlist
       
   elif   date > 121838400:
      if chatter > 0: print 'date > 121838400'
      if   filter == 'uvw1': return 957.691+r2d, 1039.086+r2d
      elif filter == 'wh'  : return 956.000+r2d, 1039.775+r2d
      elif filter == 'v'   : return 958.918+r2d, 1039.994+r2d 
      elif filter == 'b'   : return 958.273+r2d, 1040.032+r2d 
      elif filter == 'u'   : return 963.189+r2d, 1038.426+r2d
      elif filter == 'uvm2': return 956.388+r2d, 1039.235+r2d 
      elif filter == 'uvw2': return 957.717+r2d, 1040.371+r2d
      elif filter == 'w1'  : return 957.691+r2d, 1039.086+r2d
      elif filter == 'm2'  : return 956.388+r2d, 1039.235+r2d 
      elif filter == 'w2'  : return 957.717+r2d, 1040.371+r2d
      elif filter == 'ug200':       
          if order == 1:
             if wave == 260: return 928.53+r2d,1002.69+r2d
          elif order == 0: return 1449.22+6.4+r2d, 707.7-10+r2d   
      elif filter == 'uc160':       
          if order == 1:
             if wave == 260: return 1025.1+r2d,945.3+r2d
          elif order == 0: return 1501.4+6.4+r2d, 593.7-10+r2d   
      elif filter == 'vg1000': 
          if order == 0: return 1506.8+6.4+r2d,664.3-10+r2d 
      elif filter == 'vc955':
          if order == 0: return 1542.5+6.4+r2d, 556.4-10+r2d
      else: return filterlist
      

   else:
      # this is the version used initially *(changed 2 june 2009)
      # DO NOT CHANGE THESE VALUES AS THE WAVECAL DEPENDS ON THEM !!!
      if   filter == 'uvw1': return 954.61+r2d, 1044.66+r2d
      elif filter == 'wh'  : return 954.51+r2d, 1043.49+r2d
      elif filter == 'v'   : return 955.06+r2d, 1045.98+r2d 
      elif filter == 'b'   : return 955.28+r2d, 1045.08+r2d 
      elif filter == 'u'   : return 960.06+r2d, 1043.33+r2d
      elif filter == 'uvm2': return 953.23+r2d, 1044.90+r2d 
      elif filter == 'uvw2': return 953.23+r2d, 1044.90+r2d
      elif filter == 'w1'  : return 954.61+r2d, 1044.66+r2d
      elif filter == 'm2'  : return 953.23+r2d, 1044.90+r2d 
      elif filter == 'w2'  : return 953.23+r2d, 1044.90+r2d
      elif filter == 'ug200':       
          if order == 1:
             if wave == 260: return 928.53+r2d,1002.69+r2d
          elif order == 0: return 1449.22+r2d, 707.7+r2d   
      elif filter == 'uc160':       
          if order == 1:
             if wave == 260: return 1025.1+27+r2d,945.3+r2d
          elif order == 0: return 1501.4+r2d, 593.7+r2d   
      elif filter == 'vg1000': 
          if order == 0: return 1506.8+r2d,664.3+r2d 
	  #elif order == 1: return 948.4+r2d, 1025.9+r2d
	  elif order == 1: return 969.3+r2d, 1021.3+r2d
      elif filter == 'vc955':
          if order == 0: return 1567+r2d, 543+r2d
	  elif order == 1: return 1063.7+r2d, 952.6+r2d
      elif filter == 'list': return filterlist
         
   return ('wh','v','b','u','uvw1','uvm2',
       'uvw2','ug200','uc160','vg1000','vc955')    
   print 'uvotgetspec.boresight error in input '


def makeXspecInput(lamdasp,countrate,error,lamda_response=None,chatter=1):
   ''' Convert the count rate spectrum per pixel into a spectrum
   on the given bins of the response function.
   
   Parameters
   ----------
   lamdasp : array
      wavelengths spectrum
   countrate : array
      count rates at wavelengths 
   error : array
      errors at wavelengths
      
   kwargs : dict
   
    - **lamda_response** : array
   
      the wavelength for the response bins
     
    - **chatter** : int
   
      verbosity
   
   Returns
   ------- 
   lambda : array
     wavelengths of the bins   
   countrate : array
     count rate in the bins
   error : array
     errors in the bins
       
   Notes
   -----    
   errors are summed as sqrt( sum (errors**2 ) )
   '''
   # calculate bin size response, data
   if lamda_response == None: 
      print 'need to read in response matrix file'
      print ' please code it up'
      return None
       
   new_countrate = np.zeros(len(lamda_response))
   new_error     = np.zeros(len(lamda_response))  
   # find bin widths
   dlamresp = lamda_response.copy()*0
   for i in range(len(dlamresp) -1): 
         dlamresp[i+1] = lamda_response[i+1] - lamda_response[i]
   dlamresp[0] = dlamresp[1]  # set width first two data bins equal (could inter/extrapolate the lot)
   dlam = lamdasp.copy()*0   
   for i in range(len(dlam) -1):
         dlam[i+1]=lamdasp[i+1] - lamdasp[i]
   dlam[0] = dlam[1]	 
   #
   for i in range(len(lamda_response)):
         # find the pixels to use that have contributions to the bin
	 lam1 = lamda_response[i] - dlamresp[i]/2.0
	 lam2 = lamda_response[i] + dlamresp[i]/2.0
	 if ( (lam1 >= (np.max(lamdasp)+dlam[len(lamdasp)-1])) ^ (lam2 <= (np.min(lamdasp)-dlam[0]))): 
	    # no count data 
	    new_countrate[i] = 0
	    if ((chatter > 2) & (i < 450) & (i > 400)) : 
	       print ' i = ',i,'  lam1 = ',lam1,' lam2 = ', lam2,' <<< counts set to zero '
	       print ' i = ',i,' term 1 ',(np.max(lamdasp)-dlam[len(lamdasp)-1])
	       print ' i = ',i,' term 2 ',(np.min(lamdasp)+dlam[0]             )
	 else:
	    if chatter > 2: print 'new bin ',i,' lam = ',lam1,' - ',lam2
	    # find the bits to add     
	    k = np.where( (lamdasp+dlam/2 > lam1) & (lamdasp-dlam/2 <= lam2) ) 
            # the countrate in a bin is proportional to its width; make sure only
	    # the part of the data array that fall within the new bin is added
	    if chatter > 2: 
	      print 'data in ',k[0],'  wavelengths ',lamdasp[k[0]]  
	      print 'counts are ',countrate[k[0]]
	    nk = len(k[0])
	    factor = np.zeros( nk )
	    for m in range(nk):  # now loop over all bins that might contribute
	       wbin1 = lamdasp[k[0][m]] - dlam[k[0][m]]/2 
	       wbin2 = lamdasp[k[0][m]] + dlam[k[0][m]]/2
	       #  width bin_form override with limits bin_to 
	       factor[m] = (np.min(np.array( (wbin2,lam2) )) - np.max(np.array((wbin1 ,lam1))))/ (wbin2-wbin1)
	       if chatter > 2 : 
	          print ' ... m = ',m,'  bin= ',wbin1,' - ',wbin2
	          print ' ... trimmed ',np.min(np.array( (wbin2,lam2) )),' - ',np.max(np.array((wbin1 ,lam1)))
            new_countrate[i] = (factor * countrate[k[0]]).sum()
            new_error[i]     = np.sqrt( (  (factor * error[k[0]])**2  ).sum() ) 
	    if chatter > 2: 
	       print ' scaled factor = ', factor
	       print ' new_countrate = ', new_countrate[i]
	       #	    	    
   # check that the total number of counts is the same	    
   print 'total counts in = ', countrate.sum()
   print 'total counts out= ', new_countrate.sum()
   #  
   return lamda_response, new_countrate, new_error


def find_zeroth_orders(filestub, ext, wheelpos, region=False,indir='./',set_maglimit=None, clobber="NO", chatter=0):
   ''' runs uvotdetect to get the zeroth orders in the detector image.
   
       grabs a source list and converts the positions to detector coordinates
       
   '''
   import os
   import pyfits
   from numpy import array, zeros, log10, where
   import datetime
   import uvotwcs
   
   if chatter > 0: print "determining positions zeroth orders from USNO-B1"
   
   if ((wheelpos == 160) ^ (wheelpos == 200)):
      grtype = "ugu"
   else:
      grtype = "ugv"  
       
   exts = repr(ext)
   gfile = indir+'/'+filestub+grtype+"_dt.img"   
   infile = indir+'/'+filestub+grtype+"_dt.img["+exts+"]"
   outfile = indir+'/'+filestub+grtype+"_"+exts+"_detect.fits"
   
   command = "uvotdetect infile="+infile+ " outfile="+outfile + \
   ' threshold=6 sexargs = "-DEBLEND_MINCONT 0.1"  '+ \
   " expopt = BETA calibrate=NO  expfile=NONE "+ \
   " clobber="+clobber+" chatter=0"
   #"+repr(chatter) 
   
   if chatter > 1: print command
   
   useuvotdetect = True
   tt = os.system(command)
   if tt != 0:
      print 'uvotdetect had a problem with this file'
      
   if not os.access(outfile,os.F_OK):  
      # so you can provide it another way
      useuvotdetect = False
   
   if useuvotdetect:
    f = pyfits.open(outfile)
    g = f[1].data
    h = f[1].header
    refid = g.field('refid')   
    rate  = g.field('rate')
    rate_err = g.field('rate_err')
    rate_bkg = g.field('rate_bkg') # counts/sec/arcsec**2
    x_img = g.field('ux_image')
    y_img = g.field('uy_image')
    a_img = g.field('ua_image')  # semi  axis
    b_img = g.field('ub_image')  # semi  axis
    theta = g.field('utheta_image') # angle of the detection ellipse
    prof_major = g.field('prof_major') 
    prof_minor = g.field('prof_minor')
    prof_theta = g.field('prof_theta')
    threshold =  g.field('threshold')  # sigma
    flags = g.field('flags')
    f.close()
   else:
    rate_bkg = array([0.08]) 
     
   hh = pyfits.getheader(gfile, ext) 
   exposure = hh['exposure']
   ra  = hh['RA_PNT']
   dec = hh['DEC_PNT']
   if chatter > 1: print "find_zeroth_orders: pointing position ",ra,dec
   #  unfortunately uvotdetect will pick up spurious stuff as well near the spectra 
   #  need real sources.
   #  get catalog sources (B magnitude most closely matches zeroth order)
   
   CALDB = os.getenv('CALDB')
   if CALDB == '': 
      print 'the CALDB environment variable has not been set'
      return None
   HEADAS = os.getenv('HEADAS')
   if HEADAS == '': 
      print 'The HEADAS environment variable has not been set'
      print 'That is needed for the uvot Ftools '
      return None
      
   zp = 19.46
   if set_maglimit == None:  
      blim = zp - log10( (abs(rate_bkg)).mean()*314. ) + zeroth_blim_offset
   else:
      blim = set_maglimit
         
   command = "scat -c ub1 -d -m3 6,"+repr(blim)+" -n 5000 -r 900 -w -x -j "+repr(ra)+"  "+repr(dec)
   
   if not os.access('search.ub1',os.F_OK):
      if chatter > 1: print command
      tt = os.system(command)   # writes the results to seach.ub1
      if tt != 0:
         print tt 
         print "could not get source list from USNO-B1; scat not present?"
   else:
      if chatter > 1: print "find_zeroth_orders: using the USNO-B1 source list from file search.ub1"
   f = open('search.ub1','r')
   lines = f.readlines()
   f.close()
   M = len(lines)
   ra    = zeros(M)
   dec   = zeros(M)
   b2mag = zeros(M)
   ondetector = zeros(M,dtype=bool)
   Xim = zeros(M)
   Yim = zeros(M)
   Xa  = zeros(M)
   Yb  = zeros(M)
   Thet= zeros(M)
   matched = zeros(M,dtype=bool)

   for i in range(M):
      x = lines[i] 
      if chatter > 4: print x
      ra[i],dec[i] = x.split()[1:3]
      b2mag[i]     = x.split()[5] 
      if chatter > 3: print i, ra[i], dec[i], b2mag[i]  
      
   # now find the image coordinates: 
   f = open('radec.txt','w')   
   for i in range(M):
      f.write("%12.7f  %12.7f \n"%(ra[i],dec[i]))
   f.close()   
   command = HEADAS+'/bin/uvotapplywcs infile=radec.txt outfile=detpix.out wcsfile=\"'\
           +gfile+'['+exts+']\" operation=WORLD_TO_PIX from=S '
   tt = os.system(command)
   if tt != 0: 
      print "find_zeroth_orders: problem with coordinate conversion catalog positions"
   
   xdim, ydim = hh['naxis1'],hh['naxis2']
   #crpix1,crpix2 = hh['crpix1'],hh['crpix2']
   wheelpos = hh['wheelpos']
   if wheelpos ==  200: defaulttheta = 151.4-180.
   if wheelpos ==  160: defaulttheta = 144.4-180.
   if wheelpos ==  955: defaulttheta = 140.5-180.
   if wheelpos == 1000: defaulttheta = 148.1-180.
   Thet -= defaulttheta
   Xa += 17.0
   Yb += 5.5
   
   # convert sky coord. to positions (Xim , Yim) , and set flag ondetector 
   f = open('detpix.out', "r")
   lines = f.readlines()
   for i in range(len(lines)):
      Xim[i], Yim[i] = (lines[i].split())[2:4]   
      # now we need to apply the distortion correction:
      Xim[i], Yim[i] = uvotwcs.correct_image_distortion(Xim[i],Yim[i],hh)
      ondetector[i] = ((Xim[i] > 8) & (Xim[i] < xdim) & (Yim[i] > 8) & (Yim[i] < ydim-8)) 
   f.close
   
   if len(lines) != M:
      print "M = ",M
      print "Problem: not enough positions on detector from number of sky positions"
   
   # find ellipse belonging to source from uvotdetect output, or make up one for all ondetector
   xacc = 10
   yacc = 6
   for i in range(M):
     if (ondetector[i] and useuvotdetect):
       kx = where ( abs(Xim[i] - x_img) < xacc )
       if len(kx[0]) != 0: 
          kxy = where( abs(Yim[i] - y_img[kx])  < yacc) 
	  if len(kxy[0]) == 1:
	     k = kx[0][kxy[0][0]]
             Xa[i]  = prof_major[k]*5.
	     Yb[i]  = prof_minor[k]*5.
	     Thet[i]= -theta[k] 
	     matched[i] = True
       else:
         # make up ellipse
	 Xa[i] = 17.0
	 Yb[i] = 5.0
	
   if region:	     
      a = datetime.date.today()
      datetime = a.isoformat()[0:4]+a.isoformat()[5:7]+a.isoformat()[8:10]
      # make region file for sources on detector
      f = open(filestub+'_'+exts+'.reg','w')
      f.write('# Region file format: DS9 version 4.1\n')
      #f.write('# written by uvotgetspec.findzerothorders python program '+datetime+'\n') 
      f.write('# Filename: '+infile+'\n')
      f.write('global color=green dashlist=8 3 width=1 font="helvetica 10 normal" select=1 highlite=1 dash=0 fixed=0 edit=1 move=1 delete=1 include=1 source=1 \n')
      f.write('physical\n')
      for i in range(M):
	 if (ondetector[i] and useuvotdetect):
	     f.write('ellipse(%12.2f,%12.2f,%12.2f,%12.2f,%12.2f)\n' % (Xim[i],Yim[i],Xa[i],Yb[i],180.-Thet[i]) )
      f.close()
      # make a second region file for sources with first order on detector [TBD]
      # the sources on the detector are Xim[ondetector] etc., 
      # matched[ondetector] are those sources which have both been found by uvotdetect and in the catalog
      # the complete list also includes sources off the detector which may have first orders on the 
      #   detector when the B magnitude > ~14.  
      # the ellipse parameters for the sources which have no uvotdetection (matched=False) are some
      #   arbitrary mean values. They should be scaled to brightness.
   return Xim,Yim,Xa,Yb,Thet,b2mag,matched,ondetector   
   
   

def spec_curvature(wheelpos,anchor,order=1,):
   '''Find the coefficients of the polynomial for the curvature.   
   
   Parameters
   ----------
   wheelpos : int, {160,200,955,1000}
      grism filter position in filter wheel
   anchor : list, array
      anchor position in detector coordinates (pixels)
   order : int
      the desired spectral order  
	 
   Returns
   -------
      Provides the polynomial coefficients for y(x). 
   
   Notes
   -----
   The curvature is defined with argument the pixel coordinate in the dispersion 
   direction with reference to the the anchor coordinates in det-img 
   coordinates. The polynomial returns the offset normal to the dispersion.
   
   - 2011-03-07 Paul Kuin, initial version 
   - 2011-08-02 fixed nominal coefficients order=1
   '''
   from scipy import interpolate
   from numpy import array
   xin = anchor[0] -104
   yin = anchor[1]  -78
   if ((wheelpos == 1000) ^ (wheelpos == 955)):
      # return y = 0 + 0.0*x coefficient
      return array([0.,0.])

   elif wheelpos == 160:

     if order == 1:

       tck_c1= [array([0.,0.,0.,0.,2048.,  2048.,  2048.,  2048.]), \
          array([0.,0.,0.,0.,  2048.,  2048.,  2048.,  2048.]), \
          array([ 0.1329227 , -0.28774943,  0.13672294, -0.18436127, -0.19086855,\
          0.23071908, -0.21803703,  0.11983982,  0.16678715, -0.2004285 ,\
          0.12813155, -0.13855324, -0.1356009 ,  0.11504641, -0.10732287,\
          0.03374111]),3,3]
	  
       tck_c2 = [array([0.,0.,0.,0.,  2048.,  2048.,  2048.,  2048.]),\
          array([0.,0.,0.,0.,  2048.,  2048.,  2048.,  2048.]),\
          array([ -3.17463632e-04,   2.53197376e-04,  -3.44611897e-04,\
         4.81594388e-04,   2.63206764e-04,  -3.03314305e-04,\
         3.25032065e-04,  -2.97050826e-04,  -3.06358032e-04,\
         3.32952612e-04,  -2.79473410e-04,   3.95150704e-04,\
         2.56203495e-04,  -2.34524716e-04,   2.75320861e-04,\
        -6.64416547e-05]),3,3]
       
       tck_c3 = [array([ 0.,0.,0.,0.,2048.,  2048.,  2048.,  2048.]),\
          array([ 0.,0.,0.,0.,2048.,  2048.,  2048.,  2048.]),\
          array([ -4.14989592e-07,   5.09851884e-07,  -4.86551197e-07,\
          1.33727326e-07,   4.87557866e-07,  -5.51120320e-07,\
          5.76975007e-07,  -3.29793632e-07,  -3.42589204e-07,\
          3.00002959e-07,  -2.90718693e-07,   5.57782883e-08,\
          2.20540397e-07,  -1.62674045e-07,   8.70230076e-08,\
         -1.13489556e-07]),3,3]
              	     
       coef = array([interpolate.bisplev(xin,yin,tck_c3),interpolate.bisplev(xin,yin,tck_c2),\
                     interpolate.bisplev(xin,yin,tck_c1), 0.])
       return coef
       
     elif order == 2: 
        tck_c0 = [array([ 0., 0., 0., 0., 1134.78683, 2048., 2048., 2048., 2048.]), \
                  array([ 0., 0., 0., 0., 871.080060, 2048., 2048., 2048., 2048.]), \
        array([-110.94246902,   15.02796289,  -56.20252149,  -12.04954456,\
        311.31851187,  -31.09148174,  -48.44676102,   85.82835905,\
        -73.06964994,   99.58445164,   46.47352776,   11.29231744,\
        -68.32631894,   88.68570087,  -34.78582366,  -33.71033771,\
          6.89774103,   25.59082616,   23.37354026,   49.61868235,\
       -438.17511696,  -31.63936231,   28.8779241 ,   51.03055925,\
         16.46852299]), 3, 3]

        tck_c1 = [array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
                  array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([ 0.52932582, -0.76118033,  0.38401924, -0.189221  , -0.45446129,\
        0.73092481, -0.53433133,  0.12702548,  0.21033591, -0.45067611,\
        0.32032545, -0.25744487, -0.06022942,  0.22532666, -0.27174491,\
        0.03352306]), 3, 3]

        tck_c2 = [array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
                  array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([ -4.46331730e-04,   3.94044533e-04,  -1.77072490e-04,\
         2.09823843e-04,   3.02872440e-04,  -6.23869655e-04,\
         5.44400661e-04,  -3.70038727e-04,  -1.60398389e-04,\
         4.90085648e-04,  -4.91436626e-04,   4.62904236e-04,\
         4.05692472e-05,  -2.34521165e-04,   3.04866621e-04,\
        -1.25811263e-04]), 3, 3]

       #tck_c0 = [array([0.,0.,  1132.60995961,  2048.,2048.]),
       #          array([0.,0.,   814.28303687,  2048.,2048.]),
       #          array([-49.34868162,  -0.22692399, -11.06660953,   5.95510567,
       #            -3.13109456,  37.63588808, -38.7797533 ,  24.43177327,  43.27243297]),1,1]
       #tck_c1 = [array([    0.,     0.,  2048.,  2048.]), 
       #          array([    0.,     0.,  2048.,  2048.]),
       #          array([ 0.01418938, -0.06999955, -0.00446343, -0.06662488]),1,1]
       #tck_c2 = [array([    0.,     0.,  2048.,  2048.]),
       #          array([    0.,     0.,  2048.,  2048.]), 
       #	 array([ -9.99564069e-05, 8.89513468e-05, 4.77910984e-05, 1.44368445e-05]),1,1]
       
        coef = array([interpolate.bisplev(xin,yin,tck_c2),interpolate.bisplev(xin,yin,tck_c1),\
                     interpolate.bisplev(xin,yin,tck_c0)])
        return coef
       
     elif order == 3: 
       # not a particularly good fit.
       tck_c0 =   [array([0.,     0.,  1101.24169141,  2048.,2048.]), 
	           array([0.,     0.,   952.39879838,  2048.,2048.]), 
		   array([ -74.75453915,    7.63095536, -131.36395787,   11.14709189,
                            -5.52089337,   73.59327202,  -57.25048374,   37.8898465 ,
                            65.90098406]), 1, 1]	  
       tck_c1 = [array([    0.,     0.,  2048.,  2048.]), 
                 array([    0.,     0.,  2048.,  2048.]), 
		 array([-0.04768498, -0.02044308,  0.02984554, -0.04408517]), 1, 1]
 
       coef = array([interpolate.bisplev(xin,yin,tck_c1),interpolate.bisplev(xin,yin,tck_c0)])		   
       return coef
       
     elif order == 0:
       tck_c0 =         [array([    0.,     0.,  1075.07521348,  2048. ,2048.]),
                  array([    0.,     0.,  1013.70915889,  2048. ,2048.]),
                  array([ 130.89087966,   25.49195385,    5.7585513 ,  -34.68684878,
                          -52.13229007, -168.75159696,  711.84382717, -364.9631271 ,
                          374.9961278 ]),1,1]
       tck_c1 =         [array([    0.,     0.,  2048.,  2048.]),
                  array([    0.,     0.,  2048.,  2048.]),
                  array([ 0.08258587, -0.06696916, -0.09968132, -0.31579981]),1,1]
		  
       coef = array([interpolate.bisplev(xin,yin,tck_c1),interpolate.bisplev(xin,yin,tck_c0)])		  
       return  coef
     else: 
       raise (ValueError)    

   elif wheelpos == 200:
   
     if order == 1:
        tck_c1 = [array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([-0.00820665, -0.06820851,  0.04475057, -0.06496112,  0.062989  , \
        -0.05069771, -0.01397332,  0.03530437, -0.17563673,  0.12602437,\
        -0.10312421, -0.02404978,  0.06091811, -0.02879142, -0.06533121,\
         0.07355998]), 3, 3]
	
        tck_c2 = [array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([  1.69259046e-04,  -1.67036380e-04,  -9.95915869e-05, \
         2.87449321e-04,  -4.90398133e-04,   3.27190710e-04, \
         2.12389405e-04,  -3.55245720e-04,   7.41048332e-04, \
        -4.68649092e-04,  -1.11124841e-04,   6.72174552e-04, \
        -3.26167775e-04,   1.15602175e-04,   5.78187743e-04, \
        -8.79488201e-04]), 3, 3]

        tck_c3 = [array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([    0.,     0.,     0.,     0.,  2048.,  2048.,  2048.,  2048.]),\
        array([  1.11106098e-07,   2.72305072e-07,  -7.24832745e-07,\
         4.65025511e-07,  -2.35416547e-07,  -3.87761080e-07,\
         1.05955881e-06,  -6.46388216e-07,   3.15103869e-07,\
         5.48402086e-07,  -1.44488974e-06,   6.52867676e-07,\
         1.14004672e-08,  -9.48879026e-07,   1.64082320e-06,\
        -8.07897628e-07]), 3, 3]

        # the linear fit fails at the right side (57020002) but is quite good otherwise:
        #tck_c1 = [array([    0.,     0.,  2048.,  2048.]), array([    0.,     0.,  2048.,  2048.]),\
        #          array([-0.02212781, -0.00873168, -0.00377861, -0.02478484]), 1, 1]
        # 
        #tck_c2 = [array([    0.,     0.,  2048.,  2048.]), array([    0.,     0.,  2048.,  2048.]),\
        #          array([ -6.75189230e-05,   6.19498966e-05,   5.22322103e-05, 7.75736030e-05]), 1, 1]
        #
        #tck_c3 = [array([    0.,     0.,  2048.,  2048.]), array([    0.,     0.,  2048.,  2048.]), \
        #          array([ -1.75056810e-09,  -3.61606998e-08,  -6.00321832e-09, -1.39611943e-08]), 1, 1] 
        coef = array([interpolate.bisplev(xin,yin,tck_c3),interpolate.bisplev(xin,yin,tck_c2),\
                     interpolate.bisplev(xin,yin,tck_c1), 0.])
        return coef
       
     elif order == 2: 
     
       tck_c0 = [array([0.,0.,   956.25596245,  2048.,2048.]),
           array([0.,0.,  1067.40622524,  2048.,2048.]),
           array([ 17.82135471,  -4.93884392,  20.55439437, -18.22869669,
        13.11429182,  41.2680039 ,   9.8050793 ,  32.72362507,  -6.56524782]), 1, 1]
	
       tck_c1 =  [array([    0.,     0.,  2048.,  2048.]),
           array([    0.,     0.,  2048.,  2048.]),
           array([ 0.02362119, -0.03992572,  0.0177935 , -0.10163929]),1, 1]
	   
       tck_c2 =  [array([    0.,     0.,  2048.,  2048.]),
           array([    0.,     0.,  2048.,  2048.]),
           array([ -6.32035759e-05,   5.28407967e-05,  -8.87338917e-06, 8.58873870e-05]),1,1]
       coef = array([interpolate.bisplev(xin,yin,tck_c2),interpolate.bisplev(xin,yin,tck_c1),\
                     interpolate.bisplev(xin,yin,tck_c0)])
       return coef
       
     elif order == 3:  
     
       tck_c0 = [array([    0.        ,     0.        ,   807.44415249,  2048.,2048.]),
                  array([    0.        ,     0.        ,  1189.77686531,  2048.,2048.]),
                  array([-5436.10353688,   218.93823252,  -254.71035527,   -24.35684969,
                   23.26131493,    51.66273635,    37.89898456,    46.77095978,
                   63.22039872]), 1, 1]

       tck_c1 = [array([    0.,     0.,  2048.,  2048.]),
                 array([    0.,     0.,  2048.,  2048.]),
                 array([-0.02591263, -0.03092398,  0.00352404, -0.01171369]), 1, 1]
       coef = array([interpolate.bisplev(xin,yin,tck_c1),interpolate.bisplev(xin,yin,tck_c0)])		   
       return coef
       
     elif order == 0:
       tck_c0 = [array([0.,0.,   798.6983833,  2048.,  2048.]),
                 array([0.,0.,  1308.9171309,  2048.,  2048.]),
                 array([ 1244.05322027,    24.35223956,  -191.8634177 ,  -170.68236661,
          -4.57013926, 20.35393124, -365.28237355,  -235.44828185, -2455.96232688]), 1, 1]
       tck_c1 =  [array([    0.,     0.,  2048.,  2048.]),
                  array([    0.,     0.,  2048.,  2048.]),
                  array([ 0.54398146, -0.04547362, -0.63454342, -0.49417562]),1,1]

       coef = array([interpolate.bisplev(xin,yin,tck_c1),interpolate.bisplev(xin,yin,tck_c0)])		  
       return  coef

     else: 
       raise (ValueError)    
       
   else:
      print 'spec_curvature: illegal wheelpos value'
      raise (ValueError)   
      

   	   
def curved_extraction(extimg,ank_c,anchor1, wheelpos, expmap=None, offset=0., \
    anker0=None, anker2=None, anker3=None, angle=None, \
    background_lower=[None,None], background_upper=[None,None],\
    trackonly=False, trackfull=False, caldefault=True, curved="noupdate", \
    poly_1=None,poly_2=None,poly_3=None, set_offset=False, \
    composite_fit=True, test=None, chatter=0, skip_field_sources=False,\
    predict_second_order=True, ZOpos=None,outfull=False, msg='',\
    fit_second=True,fit_third=True,C_1=None,C_2=None,dist12=None):
    
   '''This routine knows about the curvature of the spectra in the UV filters  
      can provide the coefficients of the tracks of the orders
      can provide a gaussian fit to the orders
      
      extimg = extracted image
      ank_c = array( [ X pos anchor, Y pos anchor, start position spectrum, end spectrum]) in extimg
      anchor1 = anchor position in original image in det coordinates
      wheelpos = filter wheel position   
      ZOpos variables defining Zeroth Order positions
      angle [req with ZOpos]
      
      override curvature polynomial coefficients with poly_1,poly_2,poly_3
      i.e., after a call to updateFitorder()

   NPMK, 2010-07-09 initial version  
         2012-02-20 There was a problem with the offset/track y1 position/borderup,borderdown consistency
	            when using a prescribed offset. Changing handling. Always make a fine yank adjustment < 3 pix. 
		    disabled for now the set_offset (it does not do anything). 
         2012-02-20 moved the call to updateFitorder() to curved_extraction. The result is that the 
	            spectrum will be extracted using the updated track parameters.		    
   '''
   import pylab as plt
   from numpy import array,arange,where, zeros,ones, asarray
   from uvotplot import plot_ellipsoid_regions
   import uvotmisc
   
   anky,ankx,xstart,xend = ank_c
   xstart -= ankx
   xend   -= ankx
   anchor2 = anchor1
   
   if test == 'cal': 
    from cal3 import get_1stOrderFit, get_2ndOrderFit ,get_3rdOrderFit, get_0thOrderFit
    from cal3 import nominaluv, clockeduv
    if wheelpos == 160: 
       curves = clockeduv
    elif wheelpos == 200:
       curves = nominaluv 
    else: 
       print "use straight extraction for V grism modes"
       return 
    if wheelpos > 300:
       return      
   
   # read the table of coefficients/get the coeeficients of the Y(dis) offsets and limits[]
   # stored with array of angles used. 
#                  ZEROTH ORDER CURVATURE
   if test == 'notyetcal':
     coef0 = get_0thOrderFit(xin=anchor2[0],yin=anchor2[1],curvedata=curves)
   else:  
     coef0 = spec_curvature(wheelpos,anchor2,order=0)
   dlim0L=-820
   dlim0U=-570
   present0=True
   if (xstart > dlim0U): 
      present0=False
      coef0 = array([0.,0.])
   if (xstart > dlim0L): dlim0L = xstart
#                    FIRST ORDER CURVATURE
   if test == 'cal':
     coef1 = get_1stOrderFit(xin=anchor2[0],yin=anchor2[1],curvedata=curves)
   else:  
     coef1 = spec_curvature(wheelpos,anchor2,order=1)
   dlim1L=-374
   dlim1U=1150
   present1=True
   if (xstart > dlim1L): dlim1L = xstart
   if (xend < dlim1U): dlim1U = xend
#                  SECOND ORDER CURVATURE
   if test == 'cal':
     coef2 = get_2ndOrderFit(xin=anchor2[0],yin=anchor2[1],curvedata=curves)
   else:  
     coef2 = spec_curvature(wheelpos,anchor2,order=2)
   dlim2L=25
   dlim2U=3000
   if (xstart > dlim2L): dlim2L = xstart
   if (xend < dlim2U): dlim2U = xend
   if (xend > dlim2L): 
      present2=True
   else: present2=False   
#                  THIRD ORDER CURVATURE
   if test == 'cal':
     coef3 = get_3rdOrderFit(xin=anchor2[0],yin=anchor2[1],curvedata=curves)
   else:  
     coef3 = spec_curvature(wheelpos,anchor2,order=3)
   dlim3L=425
   dlim3U=3000
   if (xstart > dlim3L): dlim3L = xstart
   if (xend < dlim3U): dlim3U = xend
   if (xend > dlim3L): 
      present3=True
   else: present3=False   
#    good first approximation:
   # if wheelpos == 160: 
   sig0coef=array([4.7])
   sig1coef=array([-8.22e-09, 6.773e-04, 3.338])
   #sig1coef=array([ 3.0])
   sig2coef=array([-5.44e-07, 2.132e-03, 3.662])
   sig3coef=array([0.0059,1.5])
   
# override coefficients y(x):
   if (poly_1 != None): coef1 = poly_1   
   if (poly_2 != None): coef2 = poly_2   
   if (poly_3 != None): coef3 = poly_3   
   
#===================================================================
   if chatter > 0:
      print '================== curvature fits for y =============='
      print 'zeroth order poly: ',coef0
      print 'first  order poly: ',coef1
      print 'second order poly: ',coef2
      print 'third  order poly: ',coef3
      print '======================================================'

#===================================================================

   # remove background  
   #if cval == None: cval = out_of_img_val = -1.0123456789  cval now global   
   
   bg, bg1, bg2, bgsig, bgimg, bg_limits, \
     (bg1_good, bg1_dis, bg1_dis_good, bg2_good, bg2_dis, bg2_dis_good,  bgimg_lin) \
     = findBackground(extimg,background_lower=background_lower, 
       background_upper=background_upper,yloc_spectrum=anky, chatter=2)
            
   spimg = extimg - bgimg   # output parameter bgimg
   ny,nx = spimg.shape
   
   # initialise quality array, exposure array for spectrum and flags
   quality = zeros(nx,dtype=int)
   expospec = zeros(5*nx,dtype=int).reshape(5,nx)  
   qflag = quality_flags()
   
   # get mask for zeroth orders in the way 
   if ((not skip_field_sources) & (ZOpos != None) & (angle != None)):
      Xim,Yim,Xa,Yb,Thet,b2mag,matched,ondetector = ZOpos
      
   # screen out zeroth orders in clocked grism outside the aperture
      # TBD    
      
   # find_zeroth_orders(filestub, ext, wheelpos,clobber="yes", )
      dims = asarray( extimg.shape )
      dims = array([dims[1],dims[0]])
      pivot_ori=array([(anchor1)[0],(anchor1)[1]])
      pivot= array([ank_c[1],ank_c[0]])

      # map down to 18th magnitude in B2 (use global variable uvotgetspec.background_source_mag)
      m_lim = background_source_mag
      map_all =  plot_ellipsoid_regions(Xim.copy(),Yim.copy(),Xa.copy(),Yb.copy(),Thet.copy(),\
         b2mag.copy(),matched.copy(), ondetector,pivot,pivot_ori,dims,m_lim,img_angle=angle-180.0,\
	 lmap=True,makeplot=False,chatter=chatter) 
      if chatter > 2:
         print "zeroth order map all: shape=",map_all.shape," min, max =",map_all.min(), map_all.max()	
	  
      # map down to 16th magnitude in B2 
      m_lim = 16.0
      map_strong =  plot_ellipsoid_regions(Xim.copy(),Yim.copy(),Xa.copy(),Yb.copy(),Thet.copy(),\
         b2mag.copy(),matched.copy(), ondetector,pivot,pivot_ori,dims,m_lim,img_angle=angle-180.0,\
	 lmap=True,makeplot=False,chatter=chatter) 
      if chatter > 2:
         print "zeroth order map strong: shape=",map_strong.shape," min, max =",map_strong.min(), map_strong.max()
	 	 
      if ny > 20: 
         # weak and strong sources within 
	 at1 = where(map_all[:,ny/2-10:ny/2+10].mean(1) != 1.)[0]
         quality[at1] = qflag.get('weakzeroth')
      if ny > 40:
         # strong sources
	 at2 = where(map_strong[:,ny/2-20:ny/2+20].mean(1) != 1.)[0]
         quality[at2] = qflag.get('zeroth')		 
   else:
      map = None
      print "no zeroth order contamination quality information available "	     


   # tracks   
   x = array(arange(nx))-ankx
   y = zeros(nx)+anky 
   y0 = zeros(nx)+anky 
   y1 = zeros(nx)+anky
   y2 = zeros(nx)+anky 
   y3 = zeros(nx)+anky   
   q0 = where((x >= dlim0L) & (x <= dlim0U))
   x0 = x[q0]
   if present0:  y0[q0] += polyval(coef0,x[q0])
   q1 = where((x >= dlim1L) & (x <= dlim1U))
   x1 = x[q1]
   if present1:  y1[q1] += polyval(coef1,x[q1])
   q2 = where((x >= dlim2L) & (x <= dlim2U))
   x2 = x[q2]
   if present2:  y2[q2] += polyval(coef2,x[q2])
   q3 = where((x >= dlim3L) & (x <= dlim3U))
   x3 = x[q3]
   if present3:  y3[q3] += polyval(coef3,x[q3])
   
   # refine the offset by determining where the peak in the 
   # first order falls. 
   # We NEED a map to exclude zeroth orders that fall on/near the spectrum 
   
   ny = int(ny)
   cp2 = zeros(ny)
   delpix = 20
   if wheelpos == 200: delpix=25  # the accuracy for the nominal uv anchor is not as good.
   eo = int(anky-100)
   if set_offset: 
      eo = int(offset-100)
   
   for q in q1[0]:
      if ((x[q] < 600) & (x[q] > -200) & (quality[q] == 0)):
        try:
          m0 = 0.5*ny-delpix + eo #int( (ny+1)/4) 
          m1 = 0.5*ny+delpix + eo #int( 3*(ny+1)/4)+1
          yoff = y1[q] - anky   # this is just the offset from the anchor since y1 was set to anky
          cp2[int(m0-yoff):int(m1-yoff)] += spimg[m0:m1,q].flatten()
        except:
	  print "skipping slice %5i in adjusting first order y-position"%(q)
          pass 
      	  
   y1_ank = anky + polyval(coef1,0)   
   (p0,p1), ier = leastsq(Fun1b, (cp2.max(),y1_ank), args=(cp2,arange(200),3.2) )
   yof = (y1_ank - p1) 
   print "\n *** cross-spectrum gaussian fit parameters: ",p0,p1
   print "the first anchor fit with gaussian peaks at %5.1f, and the Y correction is %5.1f" % (p1,yof)
   #### should also estimate the likely wavelength error from the offset distance p1 and print
   msg += "cross-spectrum gaussian fit parameters: (%5.1f ,%5.1f)\n" % (p0,p1)
   msg += "the first anchor fit with gaussian peaks at %5.1f, and the Y correction is %5.1f\n" % (p1,yof)
   
   # so now shift the location of the curves to match the first order uv part.
   if set_offset: 
         print "curve_extraction: used input parameter offset as a value to set offset y1(anchor) to ",anky +offset
         y0 += offset
         y1 += offset
         y2 += offset
         y3 += offset 
   else:   
      print "the first anchor fit with gaussian peaks at %5.1f, and the Y correction is %5.1f" % (p1,yof)
      y0 -= yof
      y1 -= yof
      y2 -= yof
      y3 -= yof

# OUTPUT PARAMETER  spectra, background, slit init - full dimension retained 
   # initialize
   
   sp_all    = zeros(nx) + cval   # straight slit
   bg_all    = zeros(nx) + cval   # straight slit
   
   sp_zeroth = zeros(nx) + cval   # curved extraction 
   sp_first  = zeros(nx) + cval   # curved extraction 
   sp_second = zeros(nx) + cval   # curved extraction 
   sp_third  = zeros(nx) + cval   # curved extraction 
   bg_zeroth = zeros(nx) + cval   # curved extraction 
   bg_first  = zeros(nx) + cval   # curved extraction 
   bg_second = zeros(nx) + cval   # curved extraction 
   bg_third  = zeros(nx) + cval   # curved extraction 
   
   apercorr   = zeros(5*nx).reshape(5,nx) + cval 
   borderup   = zeros(5*nx).reshape(5,nx) + cval 
   borderdown = zeros(5*nx).reshape(5,nx) + cval 
   
   fitorder = (present0,present1,present2,present3),(q0,q1,q2,q3), \
              (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
              (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
	      (x,xstart,xend,sp_all,quality)  
	       
	     
   if trackonly:   # output the coordinates on the extimg image which specify the lay of 
      # each order
      if outfull:
         return fitorder, cp2, (coef0,coef1,coef2,coef3), (bg_zeroth,bg_first,
	        bg_second,bg_third), (borderup,borderdown), apercorr  #, expospec, msg, curved
      else: return fitorder	 

   if not trackfull:

      if curved == "update":
        # the hope is, that with more data the calibration can be improved to eliminate this step
        #try:	 
          fitorder2, fval, fvalerr = updateFitorder(extimg, fitorder, wheelpos, full=True,
            predict2nd=predict_second_order, fit_second=fit_second, fit_third=fit_second,
	    C_1=C_1, C_2=C_2, d12=dist12, chatter=chatter)	      
          msg += "updated fitorder\n"
   
          (present0,present1,present2,present3),(q0,q1,q2,q3), \
              (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
              (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
	      (x,xstart,xend,sp_all,quality)  = fitorder2
	      
          # update the anchor y-coordinate	      
          ank_c[0] = y1[ank_c[1]]	      
        #except:
	#  msg += "WARNING: fit order curvature update has failed\n"
	#  curved = "curve"	      


      # default single track extraction 
      sphalfwid = 4.*sig1coef[0]
      spwid = 2*sphalfwid
      splim1 = 100+offset-sphalfwid+1
      splim2 = splim1 + spwid
      sp_all  = extimg[splim1:splim2,:].sum(axis=0).flatten()
      bg_all  = bgimg[splim1:splim2,:].sum(axis=0).flatten()
      borderup[4,:]   = splim2
      borderdown[4,:] = splim1

      if present0:
         for i in range(nx): 
            sphalfwid = trackwidth*polyval(sig0coef,x[i])
            spwid = 2*sphalfwid
            #splim1 = 100+offset-sphalfwid+1    changes 19-feb-2012
            #splim2 = splim1 + spwid
            #k1 = splim1+y0[i]-anky
	    k1 = int(y0[i] - sphalfwid + 0.5)
            k2 = k1 + int(spwid+0.5)
            if i in q0[0]: 
               sp_zeroth[i] = extimg[k1:k2,i].sum()
               bg_zeroth[i] = bgimg[k1:k2,i].sum()
               borderup[0,i]   = k2
               borderdown[0,i] = k1
	       apercorr[0,i] = x_aperture_correction(k1,k2,sig0coef,x[i],norder=0)
               if len(expmap) == 1: expospec[0,i] = expmap[0]
	       else: expospec[0,i] = expmap[k1:k2,i].mean()
      
      if present1:
         for i in range(nx): 
            sphalfwid = trackwidth *polyval(sig1coef,x[i])
            # if (x[i] < 30): sphalfwid *= bluetrackwidth
            spwid = 2*sphalfwid
            #splim1 = 100+offset-sphalfwid+1   changes 19-feb-2012
            #splim2 = splim1 + spwid           
            #k1 = int(splim1+y1[i]-anky+0.5)   
	    k1 = int(y1[i] - sphalfwid + 0.5)   
            k2 = k1 + int(spwid+0.5) 	    
            if i in q1[0]: 
               sp_first[i] = extimg[k1:k2,i].sum()
               bg_first[i] = bgimg[k1:k2,i].sum()
               borderup[1,i]   = k2
               borderdown[1,i] = k1
	       apercorr[1,i] = x_aperture_correction(k1,k2,sig1coef,x[i],norder=1)
               if len(expmap) == 1: expospec[1,i] = expmap[0]
	       else:  expospec[1,i] = expmap[k1:k2,i].mean()
	       
      if present2:
         for i in range(nx): 
            sphalfwid = trackwidth * polyval(sig2coef,x[i])
            spwid = 2*sphalfwid
            #splim1 = 100+offset-sphalfwid+1   changes 19-feb-2012
            #splim2 = splim1 + spwid
            #k1 = int(splim1+y2[i]-anky+0.5)
	    k1 = int(y2[i] - sphalfwid +0.5)
            k2 = k1 + int(spwid+0.5)
            if i in q2[0]: 
	       sp_second[i] = extimg[k1:k2,i].sum()
	       bg_second[i] = bgimg[k1:k2,i].sum()
               borderup[2,i]   = k2
               borderdown[2,i] = k1
	       apercorr[2,i] = x_aperture_correction(k1,k2,sig2coef,x[i],norder=2)
               if len(expmap) == 1: expospec[2,i] = expmap[0]
	       else:  expospec[2,i] = expmap[k1:k2,i].mean()

            y1_y2 = np.abs(0.5*(k2+k1) - 0.5*(borderup[1,i]-borderdown[1,i]))
            s1_s2 = 0.5*(np.polyval(sig1coef,x[i]) + np.polyval(sig2coef, x[i]) )
            if ( y1_y2 < s1_s2) : quality[i] += qflag.get('overlap') 
   
      if present3:
         for i in range(nx): 
            sphalfwid = trackwidth * polyval(sig3coef,x[i])
            spwid = 2*sphalfwid
            #splim1 = 100+offset-sphalfwid+1
            #splim2 = splim1 + spwid
            #k1 = int(splim1+y3[i]-anky+0.5)
	    k1 = int(y3[i] - sphalfwid +0.5)
            k2 = k1 + int(spwid+0.5)
            if i in q3[0]: 
	       sp_third[i] = extimg[k1:k2,i].sum(axis=0)
	       bg_third[i] = bgimg[k1:k2,i].sum(axis=0)
               borderup[3,i]   = k2
               borderdown[3,i] = k1
	       apercorr[3,i] = x_aperture_correction(k1,k2,sig3coef,x[i],norder=3)
               if len(expmap) == 1: expospec[3,i] = expmap[0]
	       else: expospec[3,i] = expmap[k1:k2,i].mean()

   
      if set_offset:   # correct this 
         y0 += offset
         y1 += offset
         y2 += offset
         y3 += offset 
      
      # update mask for zeroth orders in the way 
      if ((not skip_field_sources) & (ZOpos != None) & (angle != None)):
	 splim1 = y1_ank/2
         if ny > 20: 
            # weak and strong sources within 
	    at1 = where(map_all[:,splim1-10:splim1+10].mean(1) != 1.)[0]
            quality[at1] = qflag.get('weakzeroth')
         if ny > 40:
            # strong sources
	    at2 = where(map_strong[:,splim1-20:splim1+20].mean(1) != 1.)[0]
            quality[at2] = qflag.get('zeroth')		 
      
      fitorder = (present0,present1,present2,present3),(q0,q1,q2,q3), \
              (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
              (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
	      (x,xstart,xend,sp_all,quality)  
  
      if outfull:
         return fitorder, cp2, (coef0,coef1,coef2,coef3), (bg_zeroth,bg_first,
	        bg_second,bg_third), (borderup,borderdown), apercorr, expospec, msg, curved	        
      else: return fitorder	
       
   #===================
   # Now calculate the probability distributions across the orders using gaussian fits
   # this section was for development only

   if trackfull:   # fit the cross profile with gaussians; return the gaussian fit parameters 
      # output parameter gfit:
      # define output per x[i]: numpy array gfit.shape= (6,nx) of: (x,order,amplitude,y_pix_position,sig,flags) 
      gfit = np.zeros( 4*6*nx ).reshape(4,6,nx) -1   
      
      #check that y1,y2,y3 are full length arrays
      if not ( (len(y1) == nx) & (len(y2) == nx) & (len(y3) == nx) ): 
         print "FATAL error in uvotgetspec.curved_extraction array sizes wrong"

      # this parameter allows you to restrict the range along the dispersion being considered	 
      if (test == None) | (test == 'cal'): 
        ileft = 2
	irite = nx -2
      else:
        ileft = test[0]
	irite = test[1]	
      
      for i in range(ileft,irite):
         if chatter > 3: print "uvotgetspec.curved_extraction [trackfull] fitting i = %2i x=%6.2f"%(i,x[i])
         # do the zeroth order 
         if i in q0[0]: 
	    Ypos = (array( [y0[i]])).flatten()
	    Xpos = arange(i-2,i+3)
	    sigmas = sig0coef
	    (par, flag), junk = get_components(Xpos,spimg,Ypos,wheelpos,\
	                 caldefault=caldefault,sigmas=sigmas)
	    flags = str(flag[0])+str(flag[1])+str(flag[2])+str(flag[3])+str(flag[4])+str(flag[5])
	    iflags = int(flags)
	    gfit[0,:,i] = [i,0,par[0],par[1],par[2],iflags]
	    if chatter > 3: print i, par, flag

	 # do the first order  
	 if ((i in q1[0]) & (i not in q2[0])) :
	    Ypos = array( [y1[i]] ).flatten()
	    Xpos = arange(i-2,i+3)
	    sigmas = sig1coef
	    (par, flag), junk = get_components(Xpos,spimg,Ypos,wheelpos,\
	                        caldefault=caldefault,sigmas=sigmas)
	    flags = str(flag[0])+str(flag[1])+str(flag[2])+str(flag[3])+str(flag[4])+str(flag[5])
	    iflags = int(flags)
	    gfit[1,:,i] = [i,1,par[0],par[1],par[2],iflags]
	    if chatter > 3: print i, par, flag
	    
	 # do the second order  
	 if ((i in q1[0]) & (i in q2[0]) & (i not in q3[0])):
	    Ypos = array( [y1[i],y2[i]]).flatten()
	    Xpos = arange(i-3,i+4)
	    sigmas = array([ sig1coef[0], sig2coef[0] ])
	    if chatter > 3: print '++++ second order Xpos:',Xpos,'  Ypos: ', Ypos,' wheelpos ',wheelpos
	    Z = get_components(Xpos,spimg,Ypos,wheelpos,composite_fit=composite_fit,\
	        caldefault=caldefault,sigmas=sigmas)
	    par, flag = Z[0]
	    flags = str(flag[0])+str(flag[1])+str(flag[2])+str(flag[3])+str(flag[4])+str(flag[5])
	    iflags = int(flags)
	    gfit[1,:,i] = [i,1,par[0],par[1],par[2],iflags]
	    if len(par) == 6:
               gfit[2,:,i] = [i,2,par[3],par[4],par[5],iflags]
	    if chatter > 3: print i; print par[0:3]; print par[3:6]; print flag
	    
	 # do the third order  
	 if ((i in q1[0]) & (i in q2[0]) & (i in q3[0])):
	    Ypos = array([y1[i],y2[i],y3[i]]).flatten()
	    Xpos = arange(i-4,i+5)
	    sigmas = array([sig1coef[0], sig2coef[0], sig3coef[0]])
	    if chatter > 3: print '+++++ third order Xpos:',Xpos,'  Ypos: ', Ypos,' * * * 3 3 3 3 3 * * *'
	    width = abs( polyval(array([2.0e-05, 0.034, -70]),(anchor2[1]-1200.)))+5.0 # rough limits
	    
            try:
               Z = get_components(Xpos,spimg,Ypos,wheelpos,chatter=chatter,width=width,\
	           composite_fit=composite_fit,caldefault=caldefault,sigmas=sigmas)
	       par, flag = Z[0] 
	       
	    except:
	       print "failed 3rd order fitting width = ",width
               print "Ypos = ",Ypos
	       print "Xpos range ",i-4,i+5, "   sigmas = ",sigmas, " wheelpos = ",wheelpos
	       print "composite_fit:",composite_fit,"  caldefault:",caldefault
	       print par
	       print flag
	       par = array([0.,y1[i],3.,0.,y2[i],4.,0.,y3[i],6.])   
	       flag = array([9,9,9,9,9,9])
	       
	    flags = str(flag[0])+str(flag[1])+str(flag[2])+str(flag[3])+str(flag[4])+str(flag[5])
	    iflags = int(flags)
	    gfit[1,:,i] = [i,1,par[0],par[1],par[2],iflags]
	    if len(par) > 4: 
	       gfit[2,:,i] = [i,2,par[3],par[4],par[5],iflags]
	    if len(par) == 9:   
	       gfit[3,:,i] = [i,3,par[6],par[7],par[8],iflags]
	    if chatter > 3: 
	       print  i; print par[0:3] ; print par[3:6] ; print par[6:9] ; print iflags
	       
	 # thing not covered (properly): 
	 #  -- the second order falls on the first and the third order not
	 #  -- one of the orders is not on the detector
	 #  -- order overlap  
	 #  -- minus one order     
	       	      
      return fitorder, gfit, (bgimg,)

def x_aperture_correction(k1,k2,sigcoef,x,norder=None, mode='best', coi=None):
   '''Give the aperture correction factor for given sigcoef and position x 
      
      Using the measured cumulative profile normal to the dispersion 
   
   2012-02-20  Split out in preparation of non-gaussian aperture correction factor
   
   2012-10-06  Dependence on coi-factor identified as a likely parameter 
               changing the PSF (no further action)
   
   '''
   import uvotmisc
   import scipy
   import numpy as np
   
   apercorr = 1.0
   
   if norder == 0:       
      apercorr = 1.0/uvotmisc.GaussianHalfIntegralFraction( 0.5*(k2-k1)/np.polyval(sigcoef,x) )
   if norder == 1:  
     sig = np.polyval(sigcoef,x)
     xx = 0.5*(k2-k1)/sig
     if (mode == 'gaussian') | (xx > 4.5):     
        apercorr = 1.0/uvotmisc.GaussianHalfIntegralFraction( xx )
     else: 
       # 2012-02-21 PSF best fit at 3500 from cal_psf aper05+aper08 valid for 0.5 < xx < 4.5  
       # the function does not rise as steeply so has more prominent wings
       tck = (np.array([ 0. ,  0. ,  0. ,  0. ,  0.2,  0.3,  0.4,  0.5,  0.6,  0.7,  0.8,
             0.9,  1. ,  1.1,  1.2,  1.3,  1.4,  1.5,  1.6,  1.7,  1.8,  1.9,
             2. ,  2.1,  2.2,  2.3,  2.4,  2.5,  2.6,  2.7,  2.8,  2.9,  3. ,
             3.1,  3.2,  3.3,  3.4,  3.5,  3.6,  3.7,  3.8,  3.9,  4. ,  4.1,
             4.2,  4.3,  4.4,  4.5,  4.6,  4.7,  4.8,  5. ,  5. ,  5. ,  5. ]),
             np.array([ -6.45497898e-19,   7.97698047e-02,   1.52208991e-01,
         2.56482414e-01,   3.31017197e-01,   4.03222197e-01,
         4.72064814e-01,   5.37148347e-01,   5.97906198e-01,
         6.53816662e-01,   7.04346413e-01,   7.48964617e-01,
         7.87816053e-01,   8.21035507e-01,   8.48805502e-01,
         8.71348421e-01,   8.88900296e-01,   9.03143354e-01,
         9.16085646e-01,   9.28196443e-01,   9.38406001e-01,
         9.45971114e-01,   9.51330905e-01,   9.54947930e-01,
         9.57278503e-01,   9.58780477e-01,   9.59911792e-01,
         9.60934825e-01,   9.62119406e-01,   9.63707446e-01,
         9.66045076e-01,   9.69089467e-01,   9.73684854e-01,
         9.75257929e-01,   9.77453939e-01,   9.81061451e-01,
         9.80798098e-01,   9.82633805e-01,   9.83725248e-01,
         9.84876762e-01,   9.85915295e-01,   9.86929684e-01,
         9.87938594e-01,   9.88979493e-01,   9.90084808e-01,
         9.91288321e-01,   9.92623448e-01,   9.94123703e-01,
         9.96388866e-01,   9.98435907e-01,   1.00000000e+00,
         0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
         0.00000000e+00]), 3)
	 
       apercorr = 1.0/scipy.interpolate.splev( xx, tck,)
      
   if norder == 2:       
      apercorr = 1.0/uvotmisc.GaussianHalfIntegralFraction( 0.5*(k2-k1)/np.polyval(sigcoef,x) )
   if norder == 3:       
      apercorr = 1.0/uvotmisc.GaussianHalfIntegralFraction( 0.5*(k2-k1)/np.polyval(sigcoef,x) )
   return apercorr

def clipmask(f,sigclip=2.5,fpos=False):
   '''Provides mask to clip bad data.
   
   Parameters
   ----------
   f : 2D array
   
   kwargs : dict
     optional arguments
      
    - **sigclip** : float
   
      clip data at `sigma` standard deviations above the mean 
	
    - **fpos** : bool
   
      if True, clip negative values
	
   Returns
   -------
   mask : 2D array, boolean
      Array of same size as image, true where within sigclip standard
      deviations of mean.
   
   Notes
   -----
   By default infinities are clipped.
   
   The mask is iterated until it converges. So the effect of outliers 
   on the standard deviation is nil. This also means that sigma needs 
   to be chosen large enough or the standard deviation will not be 
   a good measure of the real noise in the mean. 		
		
   '''
   import numpy as np
   
   bg = f
   if fpos:
      mask = (np.isfinite(f) & (f >= 0.))
   else:
      mask = np.isfinite(f)
   m0 = len(np.where(mask)[0])
   n = 50
   bad = True
   
   while (bad & (n > 0)):
      n -= 1
      mask = abs(f - f[mask].mean()) < sigclip * f[mask].std()   
      m = len(np.where(mask)[0])
      if m == m0: bad = False
      else: m0 = m
      
   return mask          
      
def get_components(xpos,ori_img,Ypositions,wheelpos,chatter=0,caldefault=False,\
   sigmas=None,noiselevel=None,width=40.0,composite_fit=True, fiterrors = True, \
   smoothpix=1, amp2lim=None,fixsig=False,fixpos=False):
   ''' extract the spectral components for an image slice 
       at position(s) xpos (dispersion axis) using the Ypositions 
       of the orders. The value of Ypositions[0] should be the main peak.
       
       Notes: implicit assumption is that the 'y' axis is the pixel number. 
         if for some reason the data pairs are (z_i,f_meas_i) then the definition of y 
	 changes into z. 
	 
	 if the return value for the centre of the gaussian exceeds some number (sig?), 
	 then the solution is probably suspect. In that case a second fit with sig? held
	 fixed perhaps should be done.
	 
	 some tests show that the solution is very sensitive to the first guess of the 
	 position of the peak. It will even find a dip in the noise (neg amplitude) 
	 rather than the main peak or overshoot the peak if the starting guess is too far 
	 off, and fudge sigma to be large. 
	 
	 Error Flag: 
	 
	 flag[0] 0 = ok, 1=solution main peak is offset from Ypositions by more than 'sig' pixels 
	 flag[1] 0 = ok, 1=solution secondary peak is offset from Ypositions by more than 'sig' pixels
	 flag[2] 0 = ok, 1=solution third peak is offset from Ypositions by more than 'sig' pixels
	 flag[3] not used
	 flag[4] number of orders in answer
	 flag[5] error flag returned by fitting program
	 
         noiselevel:
         if the fit to the peak has a maximum < noiselevel then the peak will be removed.
	 
	 fiterrors True implies caldefault=True		   

         smoothpix: the number of pixels along dispersion to smooth over for 
	            fitting gaussians across dispersion

         amp2lim: second order prediction of a (minimum, maximum) valid for all xpos 

   NPMK, 2010-07-15 Fecit
   NPMK, 2011-08-16 adding smoothing for improved fitting   
   NPMK  2011-08-26 replace leastsq with mpfit based routines; clip image outside spectrum width
	 
   '''
   import numpy
   from numpy import array, arange,transpose, where, abs, min, zeros, atleast_1d, atleast_2d, sqrt
   try:
      from convolve import boxcar
   except:
      from stsci.convolve import boxcar
   
   xpos = atleast_1d(xpos)
   ori_img = atleast_2d(ori_img)
   Ypositions = atleast_1d(Ypositions)
   xpos = xpos.flatten()
   Ypositions = Ypositions.flatten()
   nypos = len(Ypositions)
   smoothpix = int(smoothpix)
   
   if smoothpix > 1:
      spimg = boxcar(ori_img.copy(),(smoothpix,),mode='reflect')
   else: spimg = ori_img   
   
   if sigmas == None: 
      sigmas = array([3.1,4.3,4.6])
   
   if chatter > 4:
      print "get_components: input prameter    wheelpos ", wheelpos
      print "get_components: input parameter       xpos ", xpos
      print "get_components: input parameter Ypositions ", Ypositions
      print "get_components: number of orders : ",nypos
      print "get_components: dimension input image      ", spimg.shape
      
   xpos = xpos[ where(xpos < spimg.shape[1])[0] ]  # eliminate elements outside range
   
   if len(xpos) <1:
      print "get_components: xpos must be at least one number"
      raise ValueError 
      return
   elif len(xpos) == 1: 
      f_meas = spimg[:,xpos]
      f_ori  = ori_img[:,xpos]
   else: 
      f_meas = spimg[:,xpos].mean(axis=1)
      f_ori  = ori_img[:,xpos].mean(axis=1)
   f_meas = f_meas.flatten()
   f_ori = f_ori.flatten()
   f_pos = f_meas >= 0
   f_err = 9.99e+9 * numpy.ones(len(f_meas))
   f_err[f_pos] = 1.4*sqrt(f_meas[f_pos])
   bg_mask = clipmask( f_meas, fpos=True)
   f_mask = bg_mask    
   bg = f_meas[bg_mask].mean()         

   if noiselevel == None: 
      noiselevel = f_meas[bg_mask].mean()
      if chatter > 3: print "get_components: adopted noiselevel = ", noiselevel
   
   y = arange(spimg.shape[0],dtype=float)  # pixel number 
   flag = zeros(6, dtype=int )   
   
   if caldefault:
   
      if sigmas == None:
         print "missing parameter fitorder in uvotgetspec.get_components\n"
      else:
         # the positions of the centre of the fits are given in Ypositions
         sigmaas = atleast_1d(sigmas) 	 
	 if nypos == 1: 
	    if chatter > 3: print 'len Ypositions == 1'
	    sig0 = sigmaas[0]
	    p0  = Ypositions[0]
	    a0  = max(f_meas)
	    f_mask[p0-4*sig0:p0+4*sig0] = True 
	       
	    Z = runfit1(y[f_mask],f_meas[f_mask],f_err[f_mask],bg,a0,p0,sig0,\
	               fixsig=fixsig,fixpos=fixpos)
            flag[5] = Z.status    
	    if Z.status > 0:
               [bg0,bg1,a0,p0,sig0] = Z.params
	    else:
	       if chatter > 4:
	          print "runfit1 status:",Z.status
		  print "runfit1 params:",Z.params   	       
	    if fiterrors: return  (Z.params,Z.perror,flag), (y,f_meas)  # errors in fit = Z.perror
	    else:         return ((a0,p0,sig0),flag), (y,f_meas)
	 if nypos == 2: 
	    if chatter > 3: print 'len Ypositions == 2'
	    sig0, sig1 = sigmaas[0], sigmaas[1]
	    p0, p1  = Ypositions
	    a0  = 0.9 * max(f_meas)
	    a1 = 0.5*a0 
	    f_mask[p0-4*sig0:p0+4*sig0] = True 
	    f_mask[p1-4*sig1:p1+4*sig1] = True 
	    Z = runfit2(y[f_mask],f_meas[f_mask],f_err[f_mask],bg,a0,p0,sig0,a1,p1,sig1,\
	               fixsig=fixsig,fixpos=fixpos,amp2lim=amp2lim)
	    flag[5] = Z.status
	    if Z.status > 0:
	       [bg0,bg1,a0,p0,sig0,a1,p1,sig1] = Z.params
	    if fiterrors: return  (Z.params,Z.perror,flag), (y,f_meas)  # errors in fit = Z.perror
	    else: 	  return ((a0,p0,sig0,a1,p1,sig1),flag), (y,f_meas)	    
	 if nypos == 3: 
	    if chatter > 3: print 'len Ypositions == 3'
	    sig0,sig1,sig2 = sigmaas[:]
	    p0, p1, p2  = Ypositions
	    a0  = 0.9* max(f_meas)
	    a1 = a0 
	    a2 = a1 
	    f_mask[p0-4*sig0:p0+4*sig0] = True 
	    f_mask[p2-4*sig2:p2+4*sig2] = True 
	    Z = runfit3(y[f_mask],f_meas[f_mask],f_err[f_mask],bg,a0,p0,sig0,a1,p1,sig1,a2,p2,sig2,\
	           fixsig=fixsig,fixpos=fixpos,amp2lim=amp2lim)
	    flag[5] = Z.status
	    if Z.status > 0:
	       [bg0,bg1,a0,p0,sig0,a1,p1,sig1,a2,p2,sig2] = Z.params
	    if fiterrors: return  (Z.params,Z.perror,flag), (y,f_meas)  # errors in fit = Z.perror
	    else: 	  return ((a0,p0,sig0,a1,p1,sig1,a2,p2,sig2),flag), (y,f_meas)

	 
   if wheelpos < 500 :
      sig = 6
   else:
      sig = 4
   sig0 = sig   	 
   
   Sig = sig
   # width = 40  Maximum order distance - parameter in call ?

   # start with fitting using a fixed sig 
   # to get the peaks fixed do them one by one
   
   if len(Ypositions) < 4 :
      #  FIT ONE PEAK for all observations
      # first guess single gaussian fit parameters
      a0 = f_meas.max() 
      y0 = Ypositions[0]      
      (p0_,p1), ier = leastsq(Fun1b, (a0,y0), args=(f_meas,y,sig) ) 
      # if the "solution" is wrong use the input as best guess:
      if abs(Ypositions[0] - p1) > 15:   
         p1 = y0
	 flag[0] = 3
      else:  # shift the input positions
         delpos = p1-Ypositions[0]
	 Ypositions += delpos 
      # refine the sigma with fixed centre for the peak
      (p0,sig_), ier = leastsq(Fun1a, (p0_,sig), args=(f_meas,y,p1) ) 
      if ((sig_ > 0.1*sig) &  (sig_ < 6.* sig)): 
         sig1 = sig_ 
      else: sig1 = sig	    
      Yout = ((p0,p1,sig1), flag), (y,f_meas)
      if chatter > 3:
         print "highest peak amplitude=%8.1f, position=%8.1f, sigma=%8.2f, ier flag=%2i "%(p0,p1,sig1,ier)
   else:
      print 'Error in number of orders given in Ypositions'
      return
   
   # limit acceptable range for seaching for maxima   
   q = where( (y < p1+width) & (y > p1-0.5*width) )   # if direction known, one can be set to 3*sig
   yq = y[q[0]]      
   qok = len(q[0]) > 0

   if ( (len(Ypositions) > 1) & qok ):
      # TWO PEAKS
      # double gaussian fit: remove the first peak from the data and fit the residual 
      f_meas_reduced = f_meas[q] - singlegaussian(yq, p0, p1, sig_)
      a0 = f_meas_reduced.max()
      y0 = where(f_meas_reduced == a0)[0][0]
      Y2 = (p2,p3) , ier = leastsq(Fun1b, (a0,y0) , args=(f_meas_reduced,yq,sig)) 
      if chatter > 3:
         print 'position order 2: %8.1f  shifted to %8.1f'%(p3,p3+y[q][0])
      p3 += y[q][0]
      # check that the refined value is not too far off:
      if abs(p3 - Ypositions[1]) > 15:
         if chatter > 3: print "problem p3 way off p3=",p3
         p3 = Ypositions[1]
	 flag[1] = 3
      Y2 = (p2,sig2), ier = leastsq(Fun1a, (p2,sig1), args=(f_meas_reduced,yq,p3 ))
      if not ((sig2 > 0.25*sig1) &  (sig2 < 4.* sig1)):  
         sig2 = sig1	
	 newsig2 = False    
      else:
         # keep sig2
         newsig2 = True	 
      if chatter > 3:
         print "second highest peak amplitude=%8.1f, position=%8.1f, sigma=%8.2f ; ier flag=%2i "%(p2,p3,sig2, ier)
      Yout = ((p0,p1,sig1,p2,p3,sig2),flag), (y,q,f_meas,f_meas_reduced)

   if ((len(Ypositions) > 2) & qok ):
      # triple gaussian fit: removed  the second peak from the data 
      (p0,p1,sig1,p2,p3,sig2), ier = \
          leastsq(Fun2, (p0,p1,sig1,p2,p3,sig2) , args=(f_meas[q],y[q]))
      if chatter > 3: 
         print "fit double gaussian (%8.2f,%8.2f,%8.2f, %8.2f,%8.2f,%8.2f)"%\
         (p0,p1,sig1,p2,p3,sig2) 
      f_meas_reduced = f_meas[q] - doublegaussian(yq,p0,p1,sig1,p2,p3,sig2)
      if not newsig2:
         y0 = Ypositions[2]
	 a0 = 10*noiselevel
      else:
         a0 = f_meas_reduced.max()
         y0 = y[q][where(f_meas_reduced == a0)[0][0]]
	 if chatter > 3: print "third order input fit: amplitude = %8.2f, position = %8.2f"%(a0,y0)
      sig3 = 2*sig2    
      Y3 = (p4,p5), ier = leastsq(Fun1b, (a0,y0) , args=(f_meas_reduced,y[q],sig3))
      p5 += y[q][0]
      if abs(p5-Ypositions[2]) > 15: 
         p5 = Ypositions[2]
	 flag[2] = 3
      Y3 = (p4a,sig3), ier = leastsq(Fun1a, (p4,sig3), args=(f_meas_reduced,y[q],p5 ))
      if sig3 > 6*sig: sig3 = 2*sig2
      if chatter > 3:
         print "third highest peak amplitude=%8.1f, position=%8.1f, sigma=%8.2f, ier flag =%i "\
	   %(p4,p5,sig3,ier)
      Yout = ((p0,p1,sig1,p2,p3,sig2,p4,p5,sig),flag),(y,q,f_meas,f_meas_reduced)
      
   # now remove odd solutions  - TBD: just flagging now  
   # check that the solutions for the centre are within 'Sig' of the input 'Ypositions'
   if chatter > 2:
      print "input Ypositions: ", Ypositions 
      nposi = len(Ypositions)
    
   if len(Ypositions) < 4 :
      dy = min(abs(p1 - Ypositions))
      if dy > Sig: flag[0] += 1
   
   if ((len(Ypositions) > 1) & ( len(q[0]) > 0 )):
      dy = min(abs(p3 - Ypositions))
      if dy > Sig: flag[1] += 1
      dy = abs(p3 - p1)
      if dy < sig: 
         flag[1] += 10
	 ip = where(abs(p3-Ypositions) < 0.9*dy)[0]
	 indx = range(len(Ypositions))
	 if len(ip) == 0: 
	    print "problem with fitting peak # 2 "
	 else:   
	    indx.pop(ip[-1])
	    Ypositions = Ypositions[indx] 	 
      if p2 < noiselevel: 
         flag[1] += 20
	 ip = where(abs(p3-Ypositions) < 0.9*dy)[0]
	 if len(ip) == 0: 
	    print "problem with fitting peak # 2 "
	 else:   
	    indx = range(len(Ypositions))
	    #return (p0,p1,p2,p3), Ypositions, ip, noiselevel,dy
	    indx.pop(ip)
	    Ypositions = Ypositions[indx]
         	 
   if ((len(Ypositions) > 2) & qok):
      dy = min(abs(p5 - Ypositions))
      if dy > Sig: flag[2] += 1
      dy = abs(p5 - p1)
      if dy < sig: 
         flag[2] += 10
	 ip = where(abs(p5-Ypositions) < 0.2*dy)[0]
	 indx = range(len(Ypositions))
	 if len(ip) == 0: 
	    print "problem with fitting peak # 2 "
	 else:   
	    indx.pop(ip)
	    Ypositions = Ypositions[indx]
      if p4 < noiselevel:
         flag[2] += 20
	 ip = where(abs(p5-Ypositions) < 0.9*dy)[0]
	 if chatter > 2: print 'ip = ',ip
	 indx = range(len(Ypositions))
	 if len(ip) == 0: 
	    print "problem with fitting peak # 2 "
	 else:   
	    indx.pop(ip[-1])
	    Ypositions = Ypositions[indx]
       
      if flag[1] != 10:
         dy = abs(p5 - p3)
         if dy < sig: 
	    flag[2] += 100
	    ip = where(abs(p5-Ypositions) < 0.9*dy)[0]
	    if len(ip) == 0: 
	       print "problem with fitting peak # 2 "
	    else:   
	       indx = range(len(Ypositions))
	       indx.pop(ip[-1])
	       Ypositions = Ypositions[indx]

   if chatter > 2:
      print "flag: ",flag
      print " initial fit parameters: \n first peak:", p0, p1, sig1
      if nposi > 1: print " second peak:", p2,p3, sig2
      if nposi > 2: print " third peak:", p4,p5, sig3
      print " intermediate Ypositions: ", Ypositions
         
   if not composite_fit:      # bail out at this point 
      if len(Ypositions) == 1: 
         Y1 = ((p0,p1,sig), flag), 0
      elif len(Ypositions) == 2:
         Y1 = ((p0,p1,sig,p2,p3,sig2), flag), 0
      elif len(Ypositions) == 3:
         Y1 = ((p0,p1,sig,p2,p3,sig2,p4,p5,sig), flag), 0
      else:
         Y1 = Yout	 	 	 
      return Y1

   # free sig and refit
   
   if ( len(Ypositions) == 1) :
      # first guess single gaussian fit parameters in range given by width parameter
      a0 = p0
      y0 = p1      
      if chatter > 3: 
         print "f_meas :", transpose(f_meas)
         print "a0: %8.2f  \ny0: %8.2f \nsig0 : %8.2f "%(a0,y0,sig) 
	 print q
      params_fit, ier = leastsq(Fun1, (a0,y0,sig), args=(f_meas[q],y[q]) )
      flag[5] = 1
      flag[4] = ier
      # remove odd solutions
      return (params_fit, flag), (f_meas, y)
   
   elif (qok & (len(Ypositions) == 2) ):
      # double gaussian fit
      a0 = p0
      y0 = p1
      a1 = p2
      y1 = p3
      Y0 = params_fit, ier = leastsq(Fun2, (a0,y0,sig,a1,y1,sig) , args=(f_meas[q],y[q])) 
      flag[5]=2
      flag[4]=ier
      # remove odd solutions - TBD
      return (params_fit, flag), (f_meas, y, f_meas_reduced, q)

   elif (qok & (len(Ypositions) == 3)):
      # restricting the fitting to a smaller region around the peaks to 
      # fit will reduce the effect of broadening the fit due to noise.
      q = where( (y > p1-3.*sig1) & (y < p3+3*sig3) ) 
      # ==== 
      # triple gaussian fit   
      a0 = p0
      y0 = p1
      a1 = p2
      y1 = p3
      a2 = p4
      y2 = p5
      Y0 = params_fit, ier = leastsq(Fun3, (a0,y0,sig1,a1,y1,sig2,a2,y2,sig3) , args=(f_meas[q],y[q]))
      flag[5] = 3  # number of peaks 
      flag[4] = ier
      # remove odd solutions
      return (params_fit, flag), (f_meas, y, f_meas_reduced, q)
      
   else:
      # error in call
      print "Error in get_components Ypositions not 1,2,or 3"
      return Yout
      

def Fun1(p,y,x):
   '''compute the residuals for gaussian fit in get_components '''
   a0, x0, sig0 = p
   return y - singlegaussian(x,a0,x0,sig0)
   
def Fun1a(p,y,x,x0):
   '''compute the residuals for gaussian fit with fixed centre in get_components '''
   a0, sig0 = p
   return y - singlegaussian(x,a0,x0,sig0)
   
def Fun1b(p,y,x,sig0):
   '''compute the residuals for gaussian fit with fixed width in get_components '''
   a0, x0 = p
   return y - singlegaussian(x,a0,x0,sig0)

def Fun1c(p,y,x,x0,sig0):
   '''compute the residuals for gaussian fit with fixed centre and width in get_components '''
   a0 = p
   return y - singlegaussian(x,a0,x0,sig0)
  
def DFun1(p,y,x):
   '''There is something wrong with the return argument. Should prob be a matrix of partial derivs '''
   a0, x0, sig0 = p
   return  -Dsinglegaussian(x,a0,x0,sig0)

def Fun2(p,y,x):
   '''compute the residuals for gaussian fit in get_components '''
   a0, x0, sig0 ,a1,x1,sig1 = p
   return y - doublegaussian(x,a0,x0,sig0,a1,x1,sig1)

def Fun2b(p,y,x,sig):
   '''compute the residuals for gaussian fit in get_components for fixed sig '''
   a0, x0, a1,x1 = p
   return y - doublegaussian(x,a0,x0,sig,a1,x1,sig)

def Fun2bb(p,y,x,sig1,sig2):
   '''compute the residuals for gaussian fit in get_components for fixed sig1, and sig2 '''
   a0, x0, a1,x1 = p
   return y - doublegaussian(x,a0,x0,sig1,a1,x1,sig2)

def Fun2bc(p,y,x,x0,x1):
   '''compute the residuals for gaussian fit in get_components for fixed centre x0, x1 '''
   a0, sig0, a1,sig1 = p
   return y - doublegaussian(x,a0,x0,sig0,a1,x1,sig1)
  
def Fun2c(p,y,x,x0,sig0,x1,sig1):
   '''compute the residuals for gaussian fit in get_components for fixed centre x_i and width sig_i '''
   a0, a1 = p
   return y - doublegaussian(x,a0,x0,sig0,a1,x1,sig1)
  
def DFun2(p,y,x):
   a0, x0, sig0,a1,x1,sig1 = p
   return  -Ddoublegaussian(x,a0,x0,sig0,a1,x1,sig1)
      
def Fun3(p,y,x):
   '''compute the residuals for gaussian fit in get_components '''
   a0, x0, sig0 ,a1,x1,sig1 ,a2,x2,sig2= p
   return y - trigaussian(x,a0,x0,sig0,a1,x1,sig1,a2,x2,sig2)
      
def Fun3b(p,y,x,sig):
   '''compute the residuals for gaussian fit in get_components '''
   a0,x0,a1,x1,a2,x2 = p
   return y - trigaussian(x,a0,x0,sig,a1,x1,sig,a2,x2,sig)
   
def Fun3bb(p,y,x,sig1,sig2,sig3):
   '''compute the residuals for gaussian fit in get_components '''
   a0,x0,a1,x1,a2,x2 = p
   return y - trigaussian(x,a0,x0,sig1,a1,x1,sig2,a2,x2,sig3)
   
def Fun3c(p,y,x,x0,sig0,x1,sig1,x2,sig2):
   '''compute the residuals for gaussian fit in get_components for fixed centre x_i and width sig_i '''
   a0, a1, a2 = p
   return y - trigaussian(x,a0,x0,sig0,a1,x1,sig1,a2,x2,sig2)
  
def DFun3(p,y,x):
   a0, x0, sig0,a1,x1,sig1,a2,x2,sig2 = p
   return  -Dtrigaussian(x,a0,x0,sig0,a1,x1,sig1,a2,x2,sig2)

def singlegaussian(x, a0, x0, sig0 ):
   '''
   The function returns the gaussian function 
   on array x centred on x0 with width sig0 
   and amplitude a0
   '''
   x = np.atleast_1d(x)
   f = 0. * x.copy()
   q = np.where( np.abs(x-x0) < 4.*sig0 )
   f[q] = a0 * np.exp( - ((x[q]-x0)/sig0)**2 )  
   return f
    
def Dsinglegaussian(x, a0, x0, sig0):
   '''partial derivative of singlegaussian to all parameters'''
   f = singlegaussian(x, a0, x0, sig0)
   dfda0 = f/a0
   dfdx0 = 2*x0*(x-x0)*f/sig0**2
   dfdsig0 = 2*f*(x-x0)**2/sig0**3
   return dfda0, dfdx0, dfdsig0

def doublegaussian(x, a0, x0, sig0, a1, x1, sig1 ):
   '''
   The function returns the double gaussian function 
   on array x centred on x0 and x1 with width sig0 and sig1
   and amplitude a0, and a1
   '''
   x = np.atleast_1d(x)
   f1 = 0. * x.copy()
   f2 = 0. * x.copy()
   q = np.where( np.abs(x-x0) < 4.*sig0 )
   f1[q] = a0 * np.exp( - ((x[q]-x0)/sig0)**2 )
   q = np.where( np.abs(x-x1) < 4.*sig1)  
   f2[q] = a1 * np.exp( - ((x[q]-x1)/sig1)**2 ) 
   f = f1+f2   
   return f

def trigaussian(x, a0, x0, sig0, a1, x1, sig1, a2, x2, sig2 ):
   '''
   The function returns the triple gaussian function 
   on array x centred on x0, x1, x2 with width sig0, sig1, sig2
   and amplitude a0,a1, a2.   :
   '''
   x = np.atleast_1d(x)
   f0 = 0. * x.copy()
   f1 = 0. * x.copy()
   f2 = 0. * x.copy()
   q = np.where(np.abs( x-x0 ) < 4.*sig0)
   f0[q] = a0 * np.exp( - ((x[q]-x0)/sig0)**2 ) 
   q = np.where(np.abs( x-x1 ) < 4.*sig1)  
   f1[q] = a1 * np.exp( - ((x[q]-x1)/sig1)**2 )
   q= np.where( np.abs(x-x2) < 4.*sig2)
   f2[q] = a2 * np.exp( - ((x[q]-x2)/sig2)**2 )
   f = f0 + f1 + f2 
   return f

def Ddoublegaussian(x, a0, x0, sig0, a1, x1, sig1):
   '''partial derivative of doublegaussian to all parameters'''
   f = singlegaussian(x, a0, x0, sig0)
   dfda0 = f/a0
   dfdx0 = 2*x0*(x-x0)*f/sig0**2
   dfdsig0 = 2*f*(x-x0)**2/sig0**3
   f = singlegaussian(x, a1, x1, sig1)
   dfda1 = f/a1
   dfdx1 = 2*x1*(x-x1)*f/sig1**2
   dfdsig1 = 2*f*(x-x1)**2/sig1**3
   return dfda0, dfdx0, dfdsig0, dfda1, dfdx1, dfdsig1
   
def gaussPlusPoly(x, a0, x0, sig0, b, n=2):
   '''compute function gaussian*polynomial(n) '''
   f = singlegaussian(x, a0, x0, sig0 ) * (b[2]+(b[1]+b[0]*x)*x)
   return f
   
def DgaussPlusPoly(x, a0, x0, sig0, b, n=2):
   '''compute Jacobian for gaussPlusPoly '''
   dfda0, dfdx0, dfdsig0 = (Dsinglegaussian(x, a0, x0, sig0) ) * (b[2]+(b[1]+b[0]*x)*x)
   dfdb2 = 0
   dfdb1 = (singlegaussian(x, a0, x0, sig0) ) *  b[1]
   dfdb0 = (singlegaussian(x, a0, x0, sig0) ) *  2*b[2]*x 
   return (dfda0, dfdx0, dfdsig0, dfdb2, dfdb1,dfdb0)


def pixdisFromWave(C_1,wave):
   ''' find the pixel distance from the given wavelengths for first order uv grism'''
   from numpy import polyval, polyfit, linspace, where
   if C_1[-2] < 4.5: d = linspace(-370,1300, num=100)
   else: d = linspace(-360,550,num=100)
   w = polyval(C_1,d)
   w1 = min(wave) - 100
   w2 = max(wave) + 100
   q =  where( (w > w1) & (w < w2) )
   Cinv = polyfit(w[q],d[q],4)
   return  polyval(Cinv,wave)  
   
def quality_flags(): 
   '''Definition of quality flags for UVOT grism '''
   flags = dict(
   good=0,         # data good, but may need COI correction
   bad=1,          # data dropout or bad pixel
   zeroth=2,       # strong zeroth order too close to/overlaps spectrum
   weakzeroth=4,   # weak zeroth order too close to/overlaps spectrum
   first=8,        # other first order overlaps and brighter than BG + 5 sigma of noise 
   overlap=16       # orders overlap to close to separate (first, second) or (first second and third)
   )   
   return flags
   
def plotSecondOrder(dis,C_2,anker,anker2, spnet, scale=False):
   '''
   The aim of this procedure is to plot 
   the spectrum with the second order wavelength scale.
   
   Second order brightness scaling (scale = True)
   
   '''
   from pylab import plot, polyval
   # catch when anker2 = NaN
   # tbd.
   D = np.sqrt((anker[0]-anker2[0])**2+(anker[1]-anker2[1])**2)
   dis2 = dis-D
   p = np.where( np.abs(dis2) == np.abs(dis2).min() )
   p1 = p[0] - 700
   p2 = len(dis2)
   aa = range(p1,p2)
   plot( polyval(C_2,dis2[aa]),spnet[aa])

def secondOrderPSF_FWHM(wavelength, C_2inv, units = 'angstroem'):
   ''' returns the second order PSF FWHM  
       in A (or pixels when units = 'pixels')
       C_2inv = inverse function of dispersion coefficients for the second order
      
       Although the PSF is horse-shoe shaped, the PSF fit is by a gaussian.
   '''
   w = [1900.,2000,2100,2200,2300,2530,2900,4000]
   FWHM = [5.9,6.5,7.7,8.7,10,14,22,63]
   a = np.polyfit(w,FWHM,2)
   pix2lam = 1.76  # this could be improved using the actual dispersion relation
   # dis = np.polyval(C_2inv,wavelength)
   # pix2lam = np.polyval(C_2,dis+1) - np.polyval(C_2,dis)
   if units == 'pixels': 
      return np.polyval(a,wavelength)
   elif units == 'angstroem':
      return np.polyval(a,wavelength) * pix2lam   

def response21_grcal(wave):
   '''
   to get 2nd order counts per bin multiply first order peak counts/bin with 
   the result of this function 
   
   broad band measurements with band width > resolution 
   let band width D_lam = (lambda_max-lambda_min)
   first order pixel ~ 3.1 A/pix 
   second order pixel ~ 1.7 A/pix
   so first order CR/pix ~ CR1_band / 3.1 
   and second order CR/pix ~ CR2_band /1 .7
   EWratio = CR2_band/CR1_band
   so # pix/band =  d_lam / 3.1 for first order and d_lam/1.7 for second order 
   so in second order pix the CR(2)/pix = CR(1)* (d_lam/3.1) / (d_lam/1.7) * EWratio
      = CR(1) * (1.7/3.2) * EW ratio 
   ''' 
   from numpy import array, exp, polyfit, log, polyval 
   wmean = array([1925.,2225,2650])
   EWratio = array([0.80,0.42,0.22])  # ratio of broad band response ground cal nominal
   EWratio_err= array([0.01,0.01,0.005])  # error   
   C1_over_C2 = 3.2/1.7 # ratio of pixel scales (1)/(2)   
   a = polyfit(wmean,log(EWratio),2) # logarithmic fit
   EW2 = exp( polyval(a, wave) ) # return ratio 
   return EW2/C1_over_C2
   
def response21_firstcal(wave,wheelpos=160):
   '''Second order flux calibration relative to first order based on
      effective areas from 2011-12-18 at offset position uv clocked grism 
      
      Near the centre (default position) of the detector, the second order 
      flux is overestimated. A better value there is perhaps half the predicted
      value, though the exact number is impossible to determine at present.
       '''
   import numpy as np 
   from scipy import interpolate   
   
   print "2nd order response based on offset position uv clocked at (1600,1600)_DET \n"
   #if wheelpos != 160:
   #   do whatever
   #
   #   return R21
   coef = np.array([  3.70653066e-06,  -9.56213490e-03,   5.77251517e+00]) 
   # ratio (sp_2/\AA)/ (sp_1/\AA)
   R21 = 1./np.polyval(coef,wave)
   if (np.min(wave) < 1838.): 
      q = (wave < 1839.)
      wav = np.array([1690, 1691, 1692, 1693, 1694, 1695, 1696, 1697, 1698, 1699, 1700,
       1701, 1702, 1703, 1704, 1705, 1706, 1707, 1708, 1709, 1710, 1711,
       1712, 1713, 1714, 1715, 1716, 1717, 1718, 1719, 1720, 1721, 1722,
       1723, 1724, 1725, 1726, 1727, 1728, 1729, 1730, 1731, 1732, 1733,
       1734, 1735, 1736, 1737, 1738, 1739, 1740, 1741, 1742, 1743, 1744,
       1745, 1746, 1747, 1748, 1749, 1750, 1751, 1752, 1753, 1754, 1755,
       1756, 1757, 1758, 1759, 1760, 1761, 1762, 1763, 1764, 1765, 1766,
       1767, 1768, 1769, 1770, 1771, 1772, 1773, 1774, 1775, 1776, 1777,
       1778, 1779, 1780, 1781, 1782, 1783, 1784, 1785, 1786, 1787, 1788,
       1789, 1790, 1791, 1792, 1793, 1794, 1795, 1796, 1797, 1798, 1799,
       1800, 1801, 1802, 1803, 1804, 1805, 1806, 1807, 1808, 1809, 1810,
       1811, 1812, 1813, 1814, 1815, 1816, 1817, 1818, 1819, 1820, 1821,
       1822, 1823, 1824, 1825, 1826, 1827, 1828, 1829, 1830, 1831, 1832,
       1833, 1834, 1835, 1836, 1837, 1838, 1839])
      ratio = np.array([ 0.258639  ,  0.26471343,  0.27042023,  0.27579628,  0.28086127,
        0.28533528,  0.28957406,  0.29359907,  0.29742921,  0.3010812 ,
        0.30456987,  0.30790845,  0.31110877,  0.3141814 ,  0.31713589,
        0.31998082,  0.32010247,  0.32081151,  0.32181713,  0.32280622,
        0.32377967,  0.32473829,  0.32568282,  0.32661395,  0.32753234,
        0.32843857,  0.32933322,  0.33021679,  0.33108977,  0.33195263,
        0.33243225,  0.33252353,  0.33262903,  0.33274794,  0.3328795 ,
        0.33302301,  0.33317782,  0.33334329,  0.33351887,  0.33370401,
        0.3338982 ,  0.33410098,  0.3343119 ,  0.33458345,  0.33498466,
        0.33538817,  0.33579382,  0.33620149,  0.33661104,  0.33702235,
        0.3374353 ,  0.33891465,  0.34053073,  0.3421217 ,  0.34368845,
        0.34663769,  0.35000718,  0.35334531,  0.35665266,  0.3599298 ,
        0.3631773 ,  0.36639568,  0.36958547,  0.37274719,  0.37588132,
        0.37898836,  0.38206878,  0.38512304,  0.38815158,  0.39115485,
        0.39413328,  0.39708727,  0.40001724,  0.40292359,  0.40616969,
        0.40948579,  0.4123554 ,  0.41437097,  0.41637511,  0.41836796,
        0.42034965,  0.42232032,  0.42428008,  0.42622906,  0.42816739,
        0.43009518,  0.43201256,  0.43391964,  0.43581654,  0.43793192,
        0.44004629,  0.44215087,  0.44424574,  0.44633099,  0.44840671,
        0.45047299,  0.4525299 ,  0.45457754,  0.45661598,  0.45864531,
        0.4607006 ,  0.46279476,  0.46626514,  0.47005637,  0.47383064,
        0.47758809,  0.48132887,  0.48505311,  0.48876095,  0.49245253,
        0.49612799,  0.49978745,  0.50343106,  0.50705893,  0.5106712 ,
        0.514268  ,  0.51784944,  0.52141565,  0.52496675,  0.52850286,
        0.53264671,  0.53713253,  0.5416131 ,  0.54608843,  0.55055849,
        0.55502327,  0.55948277,  0.56393697,  0.56838586,  0.57282942,
        0.57737607,  0.58315569,  0.58892863,  0.59469489,  0.60045444,
        0.60620727,  0.61195337,  0.61769272,  0.6234253 ,  0.6291511 ,
        0.63488101,  0.64091211,  0.64694134,  0.65296866,  0.65899403,
        0.66501741,  0.67103875,  0.67705802,  0.68307519,  0.6890902 ])
      func = interpolate.interp1d(wav, ratio, kind='linear', bounds_error=False )
      R21[q] = 1./func(wave[q])	    
   return R21      

def response21(wave, version='firstcal',wheelpos=160 ):
   '''
   second over first order response per unit of angstrom
   
   input: 
      dis1 range of first order bins (pix)
      dis2 range of second order bins (pix)
   '''
   if version == 'groundcal':
      return response21_grcal(wave)
   elif version == 'firstcal':
      return response21_firstcal(wave)
   else:
      print '\Fatal Error in call response21 function\n'
      raise IOError
      return      
   
def polyinverse( coef, dis):
    ''' determine the inverse of the polynomial coefficients 
        of the same order as in input
	so  w = polyval(coef, d)
	and d = polyval(coefinv, w) 
        
	Warning
	-------
	Accuracy is not always good.	
	'''
    import numpy as np
    wav = np.polyval(coef, dis)
    norder = np.array([len(coef)-1,len(dis)-1])
    norder = np.array([norder.max(),9]).min()
    coef_inv = np.polyfit(wav, dis, norder)  
    return coef_inv
    
def pix_from_wave( disp, wave,spectralorder=1 ):
   '''Get the pixel coordinate from wavelengths and dispersion.
    
   Parameters
   ----------
   disp : list
     the dispersion polynomial coefficients
   wave : array-like
     wavelength
   kwargs : disp
   - **spectralorder** : int
     the spectral order number
   
   returns
   ------- 
   pix : array-like
     pixel distance as
   
   Note
   ----
   polyinverse() was used which is inaccurate
   
   example
   -------
   d = pix_from_wave([3.2,2600.], lambda ) 
   
   '''    
   from scipy import interpolate
   import numpy as np
   
   wave = np.asarray( wave )
   wave = np.atleast_1d(wave)
   wone = np.ones(len(wave))
   
   if spectralorder == 1:
     # initial guess
     dinv = polyinverse( disp, np.arange(-370,1150) )
     d = np.polyval(dinv, wave )
     dp = np.polyval(dinv, wave+1.0 )
     dpdw = dp-d
     count = 100
     
     while (np.abs(np.polyval(disp,d) - wave) > 0.5 * wone).all() | count > 0:
     
        dw = np.polyval(disp,d) - wave
	d -= dpdw*dw*0.5 
	
	count -= 1
        
     return d
     
   if spectralorder == 2:
     # initial guess
     dinv = polyinverse( disp, np.arange(-640,1300) )
     d = np.polyval(dinv, wave )
     dp = np.polyval(dinv, wave+1.0 )
     dpdw = dp-d
     count = 100
     
     while (np.abs(np.polyval(disp,d) - wave) > 0.5 * wone).all() | count > 0:
     
        dw = np.polyval(disp,d) - wave
	d -= dpdw*dw*0.5 
	
	count -= 1
        
     return d

   pix = np.polyval( disp, wave )
   return   



def predict_second_order(dis,spnet,C_1,C_2,d12,qual,dismin,dismax,wheelpos):
   '''Predict the second order flux in the given wavelength range
   
   Parameters
   ----------
      spnet[dis] : array-like
         extracted spectrum of first order (with possibly higher order contributions)
         Assume anchor for dis=0, dis in pix units
      C_1, C_2 : list, ndarray
         dispersion coefficients for the first and second order
      d12 : float
         distance in pix between anchor and second order reference point 
      qual[dis] : array-like
        quality extracted spectrum 
      dismin,dismax : float
        define the pixel range for the wavelength range of the first order
      wheelpos : int {160,200,955,1000}
        position filter wheel 
      
   calling function 
      response21 is giving second over first order response for bins determined by dis 
      polyinverse determines the inverse of the polynomial coefficients
      
   returns
   -------
      sp2[dis] : array-like
          second order flux
      wave2[dis] : array-like
          second order wavelength    

   Notes
   -----
   used by response21() is giving second over first order response for bins determined by dis 
   polyinverse determines the inverse of the polynomial coefficients

   '''   
   import numpy as np
   from numpy import where, searchsorted
   
   dis   = np.asarray(1.0*dis)  # ensure floating point array
   spnet = np.asarray(spnet)
   qual  = np.asarray(qual)
      
   wave   = np.polyval(C_1,dis)
   wmin   = np.polyval(C_1,dismin)
   wmax   = np.polyval(C_1,dismax)
   
   dis2   = dis[where(dis > 1)] - d12
   wav2   = np.polyval(C_2,dis2)
   n2b = wav2.searchsorted(wmin)
   dis2 = dis2[n2b:]
   wav2 = wav2[n2b:]
   
   # determine the inverse of the dispersion on the domain with wmin< wav2 < wmax
   #C_1inv = polyinverse(C_1,dis )
   #C_2inv = polyinverse(C_2,dis2)
   
   # second order limits 
   wmin2, wmax2 = np.max(np.array([wav2[0],wmin])),wav2[-1]
   
   #compute second order prediction within the limits 
   # first order points to use to predict second order (range dis and indices)
   #dlo, dhi   = np.polyval(C_1inv,wmin2), np.polyval(C_1inv,wmax2)
   dlo, dhi   = pix_from_wave(C_1,wmin2), pix_from_wave(C_1,wmax2)
   idlo, idhi = dis.searchsorted(dlo), dis.searchsorted(dhi)
   wav1cut = wave[idlo:idhi]
   dis1cut = dis [idlo:idhi]
   qua1cut = qual[idlo:idhi]
   
   # second order dis2 corresponding to wavelength range wav1cut
   #dis2cut = polyval(C_2inv,wav1cut) 
   dis2cut = pix_from_wave(C_2, wav1cut)
   
   # find scale factor (1 pix = x \AA )
   pixscale1 = polyval(C_1, dis1cut+1) - polyval(C_1, dis1cut) 
   pixscale2 = polyval(C_2, dis1cut+1) - polyval(C_2, dis1cut)   
    
   projflux2 = spnet[idlo:idhi] * pixscale1 * response21( wav1cut,)
   projflux2bin = projflux2 /pixscale2
   
   # now interpolate  projflux2bin to find the counts/bin in the second order
   # the interpolation is needed since the array size is based on the first order 
   flux2 = interpol(dis2, dis2cut, projflux2bin) 
   qual2 = np.array( interpol(dis2, dis2cut, qua1cut) + 0.5 , dtype=int )
   
   # remove NaN values from output
   
   q = np.isfinite(wav2) & np.isfinite(dis2) & np.isfinite(flux2)
   wav2 = wav2[q]
   dis2 = dis2[q]
   flux2 = flux2[q]
   qual2 = qual2[q]
   
   return (wav2, dis2, flux2, qual2, d12), (wave, dis, spnet), 
   
''' 
    the gaussian fitting algorithm is from Craig Markward 

    I am limiting the range for fitting the position and width of the gaussians
    
    
'''
    
def runfit3(x,f,err,bg,amp1,pos1,sig1,amp2,pos2,sig2,amp3,pos3,sig3,amp2lim=None,
    fixsig=False, fixsiglim=0.2, fixpos=False,chatter=0):
   '''Three gaussians plus a linear varying background 
   
   for the rotated image, multiply err by 2.77 to get right chi-squared (.fnorm/(nele-nparm))
   '''
   import numpy as np
   import numpy.oldnumeric as Numeric
   import mpfit 
   
   if np.isfinite(bg): 
     bg0 = bg
   else: bg0 = 0.0
   
   bg1 = 0.0  
   if np.isfinite(sig1):
      sig1 = np.abs(sig1)
   else: sig1 = 3.1 
   if np.isfinite(sig2):  
      sig2 = np.abs(sig2)
   else: sig2 = 4.2
   if np.isfinite(sig3):
      sig3 = np.abs(sig3) 
   else: sig3 = 4.5      

   p0 = (bg0,bg1,amp1,pos1,sig1,amp2,pos2,sig2,amp3,pos3,sig3)
   
   if fixpos:
     pos1a = pos1-0.05
     pos1b = pos1+0.05
     pos2a = pos2-0.05
     pos2b = pos2+0.05
     pos3a = pos3-0.05
     pos3b = pos3+0.05
   else:  
   # adjust the limits to not cross half the predicted distance of orders
     pos1a = pos1-sig1
     pos1b = pos1+sig1
     pos2a = pos2-sig1
     pos2b = pos2+sig1
     pos3a = pos3-sig1
     pos3b = pos3+sig1
     # case :  pos1 < pos2 < pos3
     if (pos1 < pos2):
        pos1b = pos2a = 0.5*(pos1+pos2)
        if (pos2 < pos3):
           pos2b = pos3a = 0.5*(pos2+pos3)
        else:
           pos3 = pos2
	   pos3a = pos2 
	   pos3b = pos2b+3 
     else:  
        pos1a = pos2b = 0.5*(pos1+pos2)
        if (pos2 > pos3):
           pos2a = pos3b = 0.5*(pos2+pos3)
        else:
           pos3 = pos2
	   pos3b = pos2
	   pos3a = pos2a-3
    	 	 
   #x  = np.arange(len(f))
   
   if fixsig:
      sig1_lo = sig1-fixsiglim
      sig1_hi = sig1+fixsiglim
      sig2_lo = sig2-fixsiglim
      sig2_hi = sig2+fixsiglim
      sig3_lo = sig3-fixsiglim
      sig3_hi = sig3+fixsiglim
   else:   
   # make sure lower limit sigma is OK 
      sig1_lo = max([sig1-1  ,3.0])
      sig2_lo = max([sig2-1.4,3.5])
      sig3_lo = max([sig3-1.9,4.0])
      sig1_hi = min([sig1+1.1,4.5])
      sig2_hi = min([sig2+1.4,6.])
      sig3_hi = min([sig3+1.9,8.])
      
   # define the variables for the function 'myfunct'
   fa = {'x':x,'y':f,'err':err}
     
   if amp2lim != None:
      amp2min, amp2max = amp2lim
      parinfo = [{  \
   'limited': [1,0],   'limits' : [np.min([0.0,bg0]),0.0],'value':    bg,   'parname': 'bg0'    },{  \
   'limited': [0,0],   'limits' : [0.0,0.0],           'value'  :   0.0,   'parname': 'bg1'    },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp1,   'parname': 'amp1'   },{  \
   'limited': [1,1],   'limits' : [pos1a,pos1b],       'value'  :  pos1,   'parname': 'pos1'   },{  \
   'limited': [1,1],   'limits' : [sig1_lo,sig1_hi],   'value'  :  sig1,   'parname': 'sig1'   },{  \
   'limited': [1,0],   'limits' : [amp2min,amp2max],   'value'  :  amp2,   'parname': 'amp2'   },{  \
   'limited': [1,1],   'limits' : [pos2a,pos2b],       'value'  :  pos2,   'parname': 'pos2'   },{  \
   'limited': [1,1],   'limits' : [sig2_lo,sig2_hi],   'value'  :  sig2,   'parname': 'sig2'   },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp3,   'parname': 'amp3'   },{  \
   'limited': [1,1],   'limits' : [pos3a,pos3b],       'value'  :  pos3,   'parname': 'pos3'   },{  \
   'limited': [1,1],   'limits' : [sig3_lo,sig3_hi],   'value'  :  sig3,   'parname': 'sig3'   }]  
   else:   
      parinfo = [{  \
   'limited': [1,0],   'limits' : [np.min([0.0,bg0]),0.0],'value':    bg,   'parname': 'bg0'    },{  \
   'limited': [0,0],   'limits' : [0.0,0.0],           'value'  :   0.0,   'parname': 'bg1'    },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp1,   'parname': 'amp1'   },{  \
   'limited': [1,1],   'limits' : [pos1a,pos1b],       'value'  :  pos1,   'parname': 'pos1'   },{  \
   'limited': [1,1],   'limits' : [sig1_lo,sig1_hi],   'value'  :  sig1,   'parname': 'sig1'   },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp2,   'parname': 'amp2'   },{  \
   'limited': [1,1],   'limits' : [pos2a,pos2b],       'value'  :  pos2,   'parname': 'pos2'   },{  \
   'limited': [1,1],   'limits' : [sig2_lo,sig2_hi],   'value'  :  sig2,   'parname': 'sig2'   },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp3,   'parname': 'amp3'   },{  \
   'limited': [1,1],   'limits' : [pos3a,pos3b],       'value'  :  pos3,   'parname': 'pos3'   },{  \
   'limited': [1,1],   'limits' : [sig3_lo,sig3_hi],   'value'  :  sig3,   'parname': 'sig3'   }]  

   if chatter > 4: 
      print "parinfo has been set to: " 
      for par in parinfo: print par

   Z = mpfit.mpfit(fit3,p0,functkw=fa,parinfo=parinfo,quiet=True)
   
   '''.status :
      An integer status code is returned.  All values greater than zero can
      represent success (however .status == 5 may indicate failure to
      converge). It can have one of the following values:
 
      -16
         A parameter or function value has become infinite or an undefined
         number.  This is usually a consequence of numerical overflow in the
         user's model function, which must be avoided.
 
      -15 to -1 
         These are error codes that either MYFUNCT or iterfunct may return to
         terminate the fitting process.  Values from -15 to -1 are reserved
         for the user functions and will not clash with MPFIT.
 
      0  Improper input parameters.
         
      1  Both actual and predicted relative reductions in the sum of squares
         are at most ftol.
         
      2  Relative error between two consecutive iterates is at most xtol
         
      3  Conditions for status = 1 and status = 2 both hold.
         
      4  The cosine of the angle between fvec and any column of the jacobian
         is at most gtol in absolute value.
         
      5  The maximum number of iterations has been reached.
         
      6  ftol is too small. No further reduction in the sum of squares is
         possible.
         
      7  xtol is too small. No further improvement in the approximate solution
         x is possible.
         
      8  gtol is too small. fvec is orthogonal to the columns of the jacobian
         to machine precision.
	 '''
   
   if (Z.status <= 0): 
      print 'uvotgetspec.runfit3.mpfit error message = ', Z.errmsg
      print "parinfo has been set to: " 
      for par in parinfo: print par
   elif (chatter > 3):   
      print "\nparameters and errors : "
      for i in range(8): print "%10.3e +/- %10.3e\n"%(Z.params[i],Z.perror[i])
   
   return Z	
       
       
def fit3(p, fjac=None, x=None, y=None, err=None):
   import numpy as np
            # Parameter values are passed in "p"
            # If fjac==None then partial derivatives should not be
            # computed.  It will always be None if MPFIT is called with default
            # flag.
            # model = F(x, p)
   (bg0,bg1,amp1,pos1,sig1,amp2,pos2,sig2,amp3,pos3,sig3) = p 
	     
   model = bg0 + bg1*x + \
           amp1 * np.exp( - ((x-pos1)/sig1)**2 ) + \
           amp2 * np.exp( - ((x-pos2)/sig2)**2 ) + \
           amp3 * np.exp( - ((x-pos3)/sig3)**2 ) 
	    
            # Non-negative status value means MPFIT should continue, negative means
            # stop the calculation.
   status = 0
   return [status, (y-model)/err]
    
def runfit2(x,f,err,bg,amp1,pos1,sig1,amp2,pos2,sig2,amp2lim=None,fixsig=False,
    fixsiglim=0.2, fixpos=False,chatter=0):
   '''Three gaussians plus a linear varying background 
   
   for the rotated image, multiply err by 2.77 to get right chi-squared (.fnorm/(nele-nparm))
   '''
   import numpy as np
   import numpy.oldnumeric as Numeric
   import mpfit 
   
   if np.isfinite(bg):
      bg0 = bg
   else: bg0 = 0.0   
   bg1 = 0.0 
   if np.isfinite(sig1):
      sig1 = np.abs(sig1)
   else: sig1 = 3.1   
   if np.isfinite(sig2):
      sig2 = np.abs(sig2)
   else: sig2 = 4.2        

   p0 = (bg0,bg1,amp1,pos1,sig1,amp2,pos2,sig2)
   
   # define the variables for the function 'myfunct'
   fa = {'x':x,'y':f,'err':err}

   if fixpos:
     pos1a = pos1-0.05
     pos1b = pos1+0.05
     pos2a = pos2-0.05
     pos2b = pos2+0.05
   else:  
   # adjust the limits to not cross half the predicted distance of orders
     pos1a = pos1-sig1
     pos1b = pos1+sig1
     pos2a = pos2-sig1
     pos2b = pos2+sig1
     # case :  pos1 < pos2 
     if (pos1 < pos2):
        pos1b = pos2a = 0.5*(pos1+pos2)
     else:  
        pos1a = pos2b = 0.5*(pos1+pos2)

   if fixsig:
      sig1_lo = sig1-fixsiglim
      sig1_hi = sig1+fixsiglim
      sig2_lo = sig2-fixsiglim
      sig2_hi = sig2+fixsiglim
   else:   
   # make sure lower limit sigma is OK 
      sig1_lo = max([sig1-1  ,3.0])
      sig2_lo = max([sig2-1.4,3.5])
      sig1_hi = min([sig1+1.1,4.5])
      sig2_hi = min([sig2+1.4,6.])
     
   if amp2lim != None:
      amp2min, amp2max = amp2lim
      parinfo = [{  \
   'limited': [1,0],   'limits' : [np.min([0.0,bg0]),0.0],'value':    bg,   'parname': 'bg0'    },{  \
   'limited': [0,0],   'limits' : [0.0,0.0],           'value'  :   0.0,   'parname': 'bg1'    },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp1,   'parname': 'amp1'   },{  \
   'limited': [1,1],   'limits' : [pos1a,pos1b],       'value'  :  pos1,   'parname': 'pos1'   },{  \
   'limited': [1,1],   'limits' : [sig1_lo,sig1_hi],   'value'  :  sig1,   'parname': 'sig1'   },{  \
   'limited': [1,1],   'limits' : [amp2min,amp2max],   'value'  :  amp2,   'parname': 'amp2'   },{  \
   'limited': [1,1],   'limits' : [pos2a,pos2b],       'value'  :  pos2,   'parname': 'pos2'   },{  \
   'limited': [1,1],   'limits' : [sig2_lo,sig2_hi],   'value'  :  sig2,   'parname': 'sig2'   }]  
      
   else:  
      parinfo = [{  \
   'limited': [1,0],   'limits' : [np.min([0.0,bg0]),0.0],'value':    bg,   'parname': 'bg0'    },{  \
   'limited': [0,0],   'limits' : [0.0,0.0],           'value'  :   0.0,   'parname': 'bg1'    },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp1,   'parname': 'amp1'   },{  \
   'limited': [1,1],   'limits' : [pos1a,pos1b],       'value'  :  pos1,   'parname': 'pos1'   },{  \
   'limited': [1,1],   'limits' : [sig1_lo,sig1_hi],   'value'  :  sig1,   'parname': 'sig1'   },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp2,   'parname': 'amp2'   },{  \
   'limited': [1,1],   'limits' : [pos2a,pos2b],       'value'  :  pos2,   'parname': 'pos2'   },{  \
   'limited': [1,1],   'limits' : [sig2_lo,sig2_hi],   'value'  :  sig2,   'parname': 'sig2'   }]  

   if chatter > 4: 
      print "parinfo has been set to: " 
      for par in parinfo: print par

   Z = mpfit.mpfit(fit2,p0,functkw=fa,parinfo=parinfo,quiet=True)
   
   if (Z.status <= 0): 
      print 'uvotgetspec.runfit2.mpfit error message = ', Z.errmsg
      print "parinfo has been set to: " 
      for par in parinfo: print par
   elif (chatter > 3):   
      print "\nparameters and errors : "
      for i in range(8): print "%10.3e +/- %10.3e\n"%(Z.params[i],Z.perror[i])
   
   return Z	
       
       
def fit2(p, fjac=None, x=None, y=None, err=None):
   import numpy as np

   (bg0,bg1,amp1,pos1,sig1,amp2,pos2,sig2) = p 
	     
   model = bg0 + bg1*x + \
           amp1 * np.exp( - ((x-pos1)/sig1)**2 ) + \
           amp2 * np.exp( - ((x-pos2)/sig2)**2 ) 
	    
   status = 0
   return [status, (y-model)/err]
    
def runfit1(x,f,err,bg,amp1,pos1,sig1,fixsig=False,fixpos=False,fixsiglim=0.2,chatter=0):
   '''Three gaussians plus a linear varying background 
   
   for the rotated image, multiply err by 2.77 to get right chi-squared (.fnorm/(nele-nparm))
   '''
   import numpy as np
   import numpy.oldnumeric as Numeric
   import mpfit 
   
   if np.isfinite(bg):
      bg0 = bg
   else: bg0 = 0.00  
   
   bg1 = 0.0 
   if np.isfinite(sig1):     
      sig1 = np.abs(sig1)
   else:
      sig1 = 3.2   

   p0 = (bg0,bg1,amp1,pos1,sig1)
   
   # define the variables for the function 'myfunct'
   fa = {'x':x,'y':f,'err':err}
   
   if fixsig:
      sig1_lo = sig1-fixsiglim
      sig1_hi = sig1+fixsiglim
   else:   
   # make sure lower limit sigma is OK 
      sig1_lo = max([sig1-1 ,2.7])
      sig1_hi = min([sig1+1.1,4.5])
     
   if fixpos:
     pos1a = pos1-0.05
     pos1b = pos1+0.05
   else:  
   # adjust the limits to not cross half the predicted distance of orders
     pos1a = pos1-sig1
     pos1b = pos1+sig1
     
   parinfo = [{  \
   'limited': [1,0],   'limits' : [np.min([0.,bg0]),0.0],'value' :    bg,   'parname': 'bg0'    },{  \
   'limited': [0,0],   'limits' : [0.0,0.0],           'value'  :   0.0,   'parname': 'bg1'    },{  \
   'limited': [1,0],   'limits' : [0.0,0.0],           'value'  :  amp1,   'parname': 'amp1'   },{  \
   'limited': [1,1],   'limits' : [pos1a,pos1b],       'value'  :  pos1,   'parname': 'pos1'   },{  \
   'limited': [1,1],   'limits' : [sig1_lo,sig1_hi], 'value'  :  sig1,   'parname': 'sig1'   }]  

   if chatter > 4: 
      print "parinfo has been set to: " 
      for par in parinfo: print par

   Z = mpfit.mpfit(fit1,p0,functkw=fa,parinfo=parinfo,quiet=True)
   
   if (Z.status <= 0): print 'uvotgetspec.runfit1.mpfit error message = ', Z.errmsg
      
   return Z	
       
       
def fit1(p, fjac=None, x=None, y=None, err=None):
   import numpy as np

   (bg0,bg1,amp1,pos1,sig1) = p 
	     
   model = bg0 + bg1*x + amp1 * np.exp( - ((x-pos1)/sig1)**2 ) 
   
   status = 0
   return [status, (y-model)/err]


def getCalData(Xphi, Yphi, wheelpos,date, chatter=3,mode='bilinear',
   kx=1,ky=1,s=0,calfile=None,caldir=None):
   '''Retrieve the calibration data for the anchor and dispersion (wavelengths).
   
   Parameters
   ----------
   Xphi, Yphi : float
      input angles in degrees, from, e.g., `findInputAngle`.
      
   wheelpos : int, {160,200,955,1000}
      filter wheel position selects grism
       
   date : swifttime in seconds
      obsolete - not used
      
   kwargs : dict
     optional arguments
      
     - **calfile** : str
     
       calibration file name
     
     - **caldir** : str
     
       path of directory calibration files
     
     - **mode** : str
     
       interpolation method. Use 'bilinear' only.
     
     - **kx**, **ky** : int, {1,2,3}
       order of interpolation. Use linear interpolation only. 
       
     - **s** : float
       smoothing factor, use s=0.
       
     - **chatter** : int
       verbosity
   
   Returns
   -------
   anker, anker2 : list
      coordinate of anchor in first order.
       
   C_1, C_2 : 
      dispersion in first and second order.
       
   theta : float
      find angle of dispersion on detector as 180-theta.
      
   data : FITS_rec
      the wavecal data table  
   
   Notes
   -----
   Given the input angle Xphi, Yphi in deg., the filterwheel 
   position, and the date the spectrum was taken (in swift seconds), 
   this gets the calibration data. 
      
   The boresight must be set to the one used in deriving the calibration. 
      
   '''

   import os
   import numpy as np
   import pyfits
   from scipy import interpolate
   
   #==================================================================
   # The following calculation in reverse prepared the zemax model for 
   # the calibration table lookup. Keep for the record. UV Nominal case.
   #  first calculate the offset of the rotate the input angles due to 
   #  the difference in boresight of grism and model  
   #   = input_angle + grism_bs_angle - model_bs
   # scale = 6554.0  (deg/pix)
   # xfi = Xphi + (( 928.53-27) - (1100.5+8))/scale
   # yfi = Yphi + ((1002.69- 1) - (1100.5-4))/scale
   # rx,ry = uvotmisc.uvotrotvec(xf,yf,-64.6)
   #==================================================================
   if calfile == None:
      #
      #  get the calibration file
      #
      try:
         uvotpy = os.getenv('UVOTPY')
	 caldb  = os.getenv('CALDB')
         if uvotpy != None: 
            caldir = uvotpy+'/calfiles/'
	 elif caldb != None:
	    caldir = caldb+'/data/swift/uvota/bcf/grism/'
      except:
         print "CALDB nor UVOTPY environment variable set."     
      
      #if caldir == None: 
      #   # hardcoded development system 
      #   caldir = '/Volumes/users/Users/kuin/dev/uvotpy.latest/calfiles'
         
      if wheelpos == 200: 
         calfile = 'swugu0200wcal20041120v001.fits'
         oldcalfile='swwavcal20090406_v1_mssl_ug200.fits'
         calfile = caldir+'/'+calfile
         print 'reading UV Nominal calfile '+calfile
      elif wheelpos == 160: 
         calfile='swugu0160wcal20041120v002.fits'
         oldcalfile= 'swwavcal20090626_v2_mssl_uc160_wlshift6.1.fits'
         calfile = caldir+'/'+calfile
         print 'reading UV clocked calfile '+calfile 
      elif wheelpos == 955: 
         calfile='swugv0955wcal20041120v001.fits'
         oldcalfile= 'swwavcal20100421_v0_mssl_vc955_wlshift-8.0.fits'
         calfile = caldir+'/'+calfile
         print 'reading V Clockedcalfile '+calfile 
      elif wheelpos == 1000: 
         calfile='swugv1000wcal20041120v001.fits'
         oldcalfile= 'swwavcal20100121_v0_mssl_vg1000.fits'
         calfile = caldir+'/'+calfile
         print 'reading V Nominal calfile  '+calfile 
      else:
         print "Could not find a valid wave calibration file for wheelpos = ",wheelpos
	 print "Aborting"
         print "******************************************************************"
	 raise
         return   

   #  look up the data corresponding to the (Xphi,Yphi) point in the 
   #  calibration file (which already has rotated input arrays) 
   #    
   cal = pyfits.open(calfile)
   print "opening the calibration file with extentions\n\t",cal.info()
   hdr0 = cal[0].header
   hdr1 = cal[1].header
   data = cal[1].data
   # the rotated field grid xf,yf (inconsistent naming - use to be xrf,yrf)
   xf = xrf = data.field('PHI_X')
   N1 = int(np.sqrt( len(xf) ))
   if N1**2 != len(xf): 
      raise RuntimeError("GetCalData: calfile array not square" )
   if chatter > 2: print "GetCalData: input array size on detector is %i in x, %i in y"%(N1,N1)   
   xf = xrf = data.field('PHI_X').reshape(N1,N1)
   yf = yrf = data.field('PHI_Y').reshape(N1,N1)
   #  first order anchor and angle array
   xp1 = data.field('DETX1ANK').reshape(N1,N1)
   yp1 = data.field('DETY1ANK').reshape(N1,N1)
   th  = data.field('SP1SLOPE').reshape(N1,N1)
   if wheelpos == 955:
      #  first  order dispersion
      c10 = data.field('DISP1_0').reshape(N1,N1)
      c11 = data.field('DISP1_1').reshape(N1,N1)
      c12 = data.field('DISP1_2').reshape(N1,N1)
      c13 = data.field('DISP1_3').reshape(N1,N1)
      c14 = np.zeros(N1*N1).reshape(N1,N1)
      c1n = data.field('DISP1_N').reshape(N1,N1)
      #  second order 
      xp2 = data.field('DETX2ANK').reshape(N1,N1)
      yp2 = data.field('DETY2ANK').reshape(N1,N1) 
      c20 = data.field('DISP2_0').reshape(N1,N1)
      c21 = data.field('DISP2_1').reshape(N1,N1)
      c22 = data.field('DISP2_2').reshape(N1,N1)
      c2n = data.field('DISP2_N').reshape(N1,N1)
   else:
      #  first  order dispersion
      c10 = data.field('disp1_0').reshape(N1,N1)
      c11 = data.field('disp1_1').reshape(N1,N1)
      c12 = data.field('disp1_2').reshape(N1,N1)
      c13 = data.field('disp1_3').reshape(N1,N1)
      c14 = data.field('disp1_4').reshape(N1,N1)
      c1n = data.field('disp1_N').reshape(N1,N1)
      #  second order 
      xp2 = data.field('detx2ank').reshape(N1,N1)
      yp2 = data.field('dety2ank').reshape(N1,N1) 
      c20 = data.field('disp2_0').reshape(N1,N1)
      c21 = data.field('disp2_1').reshape(N1,N1)
      c22 = data.field('disp2_2').reshape(N1,N1)
      c2n = data.field('disp2_n').reshape(N1,N1)
   #
   #  no transform here. but done to lookup array
   #
   rx, ry = Xphi, Yphi 
   #
   #  test if within ARRAY boundaries
   #
   xfp = xf[0,:]
   yfp = yf[:,0]
   if ((rx < min(xfp)) ^ (rx > max(xfp))):
      inXfp = False
   else:
      inXfp = True
   if ((ry < min(yfp)) ^ (ry > max(yfp))):
      inYfp = False
   else:
      inYfp = True         
   #
   #    lower corner (ix,iy)
   # 
   if inXfp :
      ix  = max( np.where( rx >= xf[0,:] )[0] ) 
      ix_ = min( np.where( rx <= xf[0,:] )[0] ) 
   else:
      if rx < min(xfp): 
         ix = ix_ = 0
	 print "WARNING: point has xfield lower than calfile provides"
      if rx > max(xfp): 
         ix = ix_ = N1-1   
	 print "WARNING: point has xfield higher than calfile provides"
   if inYfp :   
      iy  = max( np.where( ry >= yf[:,0] )[0] ) 
      iy_ = min( np.where( ry <= yf[:,0] )[0] ) 
   else:
      if ry < min(yfp): 
         iy = iy_ = 0
	 print "WARNING: point has yfield lower than calfile provides"
      if ry > max(yfp): 
         iy = iy_ = 27   
	 print "WARNING: point has yfield higher than calfile provides"
   if inYfp & inXfp & (chatter > 2): 
      print 'getCalData.                             rx,         ry,     Xank,        Yank '
      print ix, ix_, iy, iy_
      print 'getCalData. gridpoint 1 position: ', xf[iy_,ix_], yf[iy_,ix_], xp1[iy_,ix_], yp1[iy_,ix_]
      print 'getCalData. gridpoint 2 position: ', xf[iy ,ix_], yf[iy ,ix_], xp1[iy ,ix_], yp1[iy ,ix_]
      print 'getCalData. gridpoint 3 position: ', xf[iy ,ix ], yf[iy ,ix ], xp1[iy ,ix ], yp1[iy ,ix ]
      print 'getCalData. gridpoint 4 position: ', xf[iy_,ix ], yf[iy_,ix ], xp1[iy_,ix ], yp1[iy_,ix ]   
   #
   #  exception at outer grid edges: 
   #
   if ((ix == N1-1) ^ (iy == N1-1) ^ (ix_ == 0) ^ (iy_ == 0)):
           
     # select only coefficient with order 4 (or 3 for wheelpos=955)
     print "IMPORTANT:"
     print "\nanchor point is outside the calibration array: extrapolating all data" 

     try: 
      if wheelpos == 955 :
        # first order solution
        q4 = np.where( c1n.flatten() == 3 )
        xf = xf.flatten()[q4]
        yf = yf.flatten()[q4]
        xp1 = xp1.flatten()[q4]
        yp1 = yp1.flatten()[q4]
        th  = th.flatten()[q4]
        c10 = c10.flatten()[q4]
        c11 = c11.flatten()[q4]
        c12 = c12.flatten()[q4]
        c13 = c13.flatten()[q4]
        c14 = np.zeros(len(q4[0]))
        c1n = c1n.flatten()[q4]
	mode = 'bisplines'
	# second order solution only when at lower or right boundary
	if (ix == N1-1) ^ (iy == 0):
          q2 = np.where( c2n.flatten() == 2 )[0]
          xp2 = xp2.flatten()[q2]
          yp2 = yp2.flatten()[q2] 
          c20 = c20.flatten()[q2]
          c21 = c21.flatten()[q2]
          c22 = c22.flatten()[q2]
          c2n = c2n.flatten()[q2]
	else:
	  N2 = N1/2
          xp2 = np.zeros(N2) 
          yp2 = np.zeros(N2) 
          c20 = np.zeros(N2)
          c21 = np.zeros(N2)
          c22 = np.zeros(N2)
          c2n = np.zeros(N2)
	  
      else: 
        q4 = np.where( c1n.flatten() == 4 )
        xf = xf.flatten()[q4]
        yf = yf.flatten()[q4]
        xp1 = xp1.flatten()[q4]
        yp1 = yp1.flatten()[q4]
        th  = th.flatten()[q4]
        c10 = c10.flatten()[q4]
        c11 = c11.flatten()[q4]
        c12 = c12.flatten()[q4]
        c13 = c13.flatten()[q4]
        c14 = np.zeros(len(q4[0]))
        c1n = c1n.flatten()[q4]
        xp2 = xp2.flatten()[q4]
        yp2 = yp2.flatten()[q4] 
        c20 = c20.flatten()[q4]
        c21 = c21.flatten()[q4]
        c22 = c22.flatten()[q4]
        c2n = c2n.flatten()[q4]
     
      # find the anchor positions by extrapolation
      anker  = np.zeros(2)
      anker2 = np.zeros(2)
      tck1x = interpolate.bisplrep(xf, yf, xp1, xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19,kx=3,ky=3,s=None) 
      tck1y = interpolate.bisplrep(xf, yf, yp1, xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19,kx=3,ky=3,s=None) 
      tck2x = interpolate.bisplrep(xf, yf, xp1, xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19,kx=3,ky=3,s=None) 
      tck2y = interpolate.bisplrep(xf, yf, yp1, xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19,kx=3,ky=3,s=None) 
     
      anker[0]  = xp1i = interpolate.bisplev(rx,ry, tck1x) 
      anker[1]  = yp1i = interpolate.bisplev(rx,ry, tck1y) 	
      anker2[0] = xp2i = interpolate.bisplev(rx,ry, tck2x) 
      anker2[1] = yp2i = interpolate.bisplev(rx,ry, tck2y) 
      
      # find the angle 	
      
      tck = interpolate.bisplrep(xf, yf, th,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
      thi = interpolate.bisplev(rx,ry, tck)
      
      # find the dispersion
      
      tck = interpolate.bisplrep(xf, yf, c10,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
      c10i = interpolate.bisplev(rx,ry, tck)
      tck = interpolate.bisplrep(xf, yf, c11,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
      c11i = interpolate.bisplev(rx,ry, tck)
      tck = interpolate.bisplrep(xf, yf, c12,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
      c12i = interpolate.bisplev(rx,ry, tck)
      tck = interpolate.bisplrep(xf, yf, c13,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
      c13i = interpolate.bisplev(rx,ry, tck)
      tck = interpolate.bisplrep(xf, yf, c14,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
      c14i = interpolate.bisplev(rx,ry, tck)
      
      if ((ix == N1-1) ^ (iy == 0)):
         tck = interpolate.bisplrep(xf, yf, c20,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
         c20i = interpolate.bisplev(rx,ry, tck)
         tck = interpolate.bisplrep(xf, yf, c21,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
         c21i = interpolate.bisplev(rx,ry, tck)
         tck = interpolate.bisplrep(xf, yf, c22,xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=3,ky=3,s=None) 
         c22i = interpolate.bisplev(rx,ry, tck)
      else:
         c20i = c21i = c22i = np.NaN 
      if chatter > 2: 
            print 'getCalData. bicubic extrapolation  ' 
            print 'getCalData. first order anchor position = (%8.1f,%8.1f), angle theta = %7.1f ' % (xp1i,yp1i,thi )
            print 'getCalData. dispersion first  order = ',c10i,c11i,c12i,c13i,c14i
	    if c20i == NaN:
	       print " no second order extracted "
	    else:   
	       print 'getCalData. second order anchor position = (%8.1f,%8.1f) ' % (xp2i,yp2i)
               print 'getCalData. dispersion second order = ', c20i,c21i, c22i
     except:	
        print "failed - ABORTING"
	raise    
        return
   else: 
   #
   #  reduce arrays to section surrounding point
   #  get interpolated quantities and pass them on 
   # 
      if mode == 'bisplines':
      # compute the Bivariate-spline coefficients
      # kx = ky =  3 # cubic splines (smoothing) and =1 is linear
         task = 0 # find spline for given smoothing factor
      #  s = 0 # 0=spline goes through the given points
      # eps = 1.0e-6  (0 < eps < 1)
         m = N1*N1
         if chatter > 2: print '\n getCalData. splines ' 
         qx = qy = np.where( (np.isfinite(xrf.reshape(m))) & (np.isfinite(yrf.reshape(m)) ) )
         tck1 = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], xp1.reshape(m)[qx],xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s) 
         tck2 = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], yp1.reshape(m)[qx],xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s) 
         xp1i = interpolate.bisplev(rx,ry, tck1)
         yp1i = interpolate.bisplev(rx,ry, tck2)
         tck3 = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], th.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         thi  = interpolate.bisplev(rx,ry, tck3)
         xp2i = 0
         yp2i = 0
             
         if chatter > 2: print 'getCalData. x,y,theta = ',xp1i,yp1i,thi, ' second order ', xp2i, yp2i
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c10.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c10i = interpolate.bisplev(rx,ry, tck)
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c11.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c11i = interpolate.bisplev(rx,ry, tck)
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c12.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c12i = interpolate.bisplev(rx,ry, tck)
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c13.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c13i = interpolate.bisplev(rx,ry, tck)
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c14.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c14i = interpolate.bisplev(rx,ry, tck)
         if chatter > 2: print 'getCalData. dispersion first order = ',c10i,c11i,c12i,c13i,c14i
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c20.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c20i = interpolate.bisplev(rx,ry, tck)
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c21.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c21i = interpolate.bisplev(rx,ry, tck)
         tck  = interpolate.bisplrep(xrf.reshape(m)[qx], yrf.reshape(m)[qy], c22.reshape(m),xb=-0.19,xe=+0.19,yb=-0.19,ye=0.19, kx=kx,ky=ky,s=s)
         c22i = interpolate.bisplev(rx,ry, tck)
         if chatter > 2: print 'getCalData. dispersion second order = ', c20i,c21i, c22i
      #
      if mode == 'bilinear':
         xp1i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), xp1 ,chatter=chatter)
         yp1i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), yp1 ,chatter=chatter)
         thi  = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), th  )# ,chatter=chatter)
         c10i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c10 )#,chatter=chatter)
         c11i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c11 )#,chatter=chatter)
         c12i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c12 )#,chatter=chatter)
         c13i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c13 )#,chatter=chatter)
         c14i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c14 )#,chatter=chatter)
         xp2i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), xp2 )#,chatter=chatter)
         yp2i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), yp2 )#,chatter=chatter)
         c20i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c20 )#,chatter=chatter)
         c21i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c21 )#,chatter=chatter)
         c22i = bilinear( rx, ry, xf[0,:].squeeze(), yf[:,0].squeeze(), c22 )#,chatter=chatter)
         if chatter > 1: 
            print 'getCalData. bilinear interpolation' 
            print 'getCalData. first order anchor position = (%8.1f,%8.1f), angle theta = %7.1f ' % (xp1i,yp1i,thi )
            print 'getCalData. dispersion first  order = ',c10i,c11i,c12i,c13i,c14i
	    print 'getCalData. second order anchor position = (%8.1f,%8.1f) ' % (xp2i,yp2i)
            print 'getCalData. dispersion second order = ', c20i,c21i, c22i
      if mode == 'interp2d':
         x1 = xf[0,:].squeeze()
	 x2 = yf[:,0].squeeze()
	 xp1i = interpolate.interp2d(x1,x2,xp1,kind='linear')
	 #same as bisplines with s=0 and k=1
	 return
	 	    
   C_1 = np.array([c14i,c13i,c12i,c11i,c10i])
   C_2 = np.array([c22i,c21i,c20i])
   # 
   # only theta for the first order is available 
   cal.close()
   anker  = np.array([xp1i,yp1i]) 
   anker2 = np.array([xp2i,yp2i]) 
   if chatter > 0: 
      print 'getCalData. anker [DET-pix]   = ', anker
      print 'getCalData. anker [DET-img]   = ', anker - [77+27,77+1]
      print 'getCalData. second order anker at = ', anker2, '  [DET-pix] ' 
   return anker, anker2, C_1, C_2, thi, data


def bilinear(x1,x2,x1a,x2a,f,chatter=0):
   '''
   Given function f(i,j) given as a 2d array of function values at
   points x1a[i],x2a[j], derive the function value y=f(x1,x2) 
   by bilinear interpolation. 
   
   requirement: x1a[i] is increasing with i 
                x2a[j] is increasing with j
   20080303 NPMK		
   '''
   import numpy as np
   
   # check that the arrays are numpy arrays
   x1a = np.asarray(x1a)
   x2a = np.asarray(x2a)
      
   #  find the index for sorting the arrays
   n1 = len(x1a)
   n2 = len(x2a)
   x1a_ind = x1a.argsort()
   x2a_ind = x2a.argsort()
   
   #  make a sorted copy
   x1as = x1a.copy()[x1a_ind]
   x2as = x2a.copy()[x2a_ind]
   
   # find indices i,j for the square containing (x1, x2)
   k1s = x1as.searchsorted(x1)-1
   k2s = x2as.searchsorted(x2)-1
   
   #  find the indices of the four points in the original array
   ki = x1a_ind[k1s]
   kip1 = x1a_ind[k1s+1]
   kj = x2a_ind[k2s]
   kjp1 = x2a_ind[k2s+1]
   if chatter > 2:
       print 'FIND solution in (x,y) = (',x1,x2,')'
       print 'array x1a[k-5 .. k+5] ',x1a[ki-5:ki+5]
       print 'array x2a[k-5 .. k+5] ',x2a[kj-5:kj+5]
       print 'length x1a=',n1,'   x2a=',n2
       print 'indices in sorted arrays = (',k1s,',',k2s,')'
       print 'indices in array x1a: ',ki, kip1
       print 'indices in array x2a: ',kj, kjp1
      
   #  exception at border:
   if ((k1s+1 >= n1) ^ (k2s+1 >= n2) ^ (k1s < 0) ^ (k2s < 0) ):
      print 'bilinear. point outside grid x - use nearest neighbor '
      if ki + 1 > len(x1a) : ki = len(x1a) - 1
      if ki < 0 : ki = 0
      if kj + 1 > len(x2a) : kj = len(x2a) - 1
      if kj < 0 : kj = 0
      return f[ki, kj]
  
   # Find interpolated solution
   y1 = f[kj  ,ki  ]
   y2 = f[kj  ,kip1]
   y3 = f[kjp1,kip1]
   y4 = f[kjp1,ki  ]
    
   t = (x1 - x1a[ki])/(x1a[kip1]-x1a[ki])
   u = (x2 - x2a[kj])/(x2a[kjp1]-x2a[kj])
   
   y = (1.-t)*(1.-u)*y1 + t*(1.-u)*y2 + t*u*y3 + (1.-t)*u*y4
   if chatter > 2: 
      print 'bilinear.                   x         y          f[x,y]    '
      print 'bilinear.   first  point ',x1a[ki  ],x2a[kj],  f[ki,kj]
      print 'bilinear.   second point ',x1a[kip1],x2a[kj],  f[kip1,kj]
      print 'bilinear.   third  point ',x1a[kip1],x2a[kjp1],  f[kip1,kjp1]
      print 'bilinear.   fourth point ',x1a[ki  ],x2a[kjp1],  f[ki,kjp1]
      print 'bilinear. fractions t, u ', t, u
      print 'bilinear. interpolate at ', x1, x2, y
   return y    
 

def findInputAngle(RA,DEC,filestub, ext, wheelpos=200, 
       lfilter='uvw1', lfilter_ext=None, 
       lfilt2=None,    lfilt2_ext=None, 
       method=None, attfile=None, 
       catspec=None, indir='./', chatter=2):
   '''Find the angles along the X,Y axis for the target distance from the bore sight.
   
   Parameters
   ----------
   RA,DEC : float
      sky position, epoch J2000, decimal degrees
      
   filestub : str
      part of filename consisting of "sw"+`obsid`
      
   ext : int
      number of the extension
      
   kwargs : dict
   
      - **wheelpos** : int, {160,200,955,1000}
      
        grism filter selected in filter wheel
	 
      - **lfilter**, **lfilt2** : str, {'uvw2','uvm2','uvw1','u','b','v'}
      
        lenticular filter name before and after grism exposure
	
      - **lfilter_ext**, **lfilt2_ext** : int
      
        lenticular filter extension before and after grism exposure 
	
      - **method** : str, {'grism_only'}
      
        if set to `grism_only`, create a temporary header to compute the 
	target input angles, otherwise use the lenticular file image.
      
      - **attfile** : str, path 
      
        full path+filename of attitude file
	
      - **catspec** : path
      
        optional full path to catalog spec file to use with uvotgraspcorr
	
      - **indir** : str, path
      
        data directory path
	
      - **chatter** : int
      
        verbosity

   Returns
   -------
   anker_as : array
      offset (DX,DY) in arcsec in DET coordinate system of the source 
      from the boresight
      needs to be converted to input rays by applying transform.
	  
   anker_field : array
      offset(theta,phi) in degrees from the axis for 
      the input field coordinates for the zemax model lookup 		 
      
   tstart : float
      start time exposure (swift time in seconds)
      
   msg : string
      messages   
   
   
   Notes
   -----
   Provided a combined observation is available in a lenticular filter and a grism 
   (i.e., they were aquired in the the same observation,) this routine determines the
   input angles from the boresight.  Assumed is that the grism and lenticular filter 
   image have the same extension. 
   
   If not a lenticular filter image was taken just before or after the grism exposure, 
   the input angles are determined from the grism aspect only. Before running this, 
   run uvotgrapcorr on the grism image when there is no lenticular filter to get a 
   better aspect solution.
         
   '''

   import numpy as np
   import pyfits

   from uvotwcs import makewcshdr 
   import os
   
   __version__ = '1.04 NPMK 20131031 NPMK(MSSL)'

   # 2010-07-11 added code to move existing uvw1 raw and sky files out of the way and cleanup afterwards.
   # npkuin@gmail.com
   msg = ""
   
   if (chatter > 0):
      print "uvotspec(",RA,DEC,filestub, ext, wheelpos, lfilter, lfilter_ext, \
       lfilt2,    lfilt2_ext, method, attfile, catspec, chatter,')'
   
   if ( (wheelpos == 160) ^ (wheelpos == 200) ): 
      gfile = indir+'/'+filestub+'ugu_dt.img'
   elif ( (wheelpos == 955) ^ (wheelpos == 1000) ): 
      gfile = indir+'/'+filestub+'ugv_dt.img'
   else: 
      print "uvotgetspec.findInputAngle: could not determine grism type" 
      return   
      
   if ((lfilter == None) & (lfilt2 == None)) | (method == 'grism_only') : 
      lfilter = 'fk' 
      method == 'grism_only'
      lfilter_ext = 1
       
   uw1rawrenamed = False
   uw1skyrenamed = False
   if method == 'grism_only':
       if chatter > 1: print "grism only method. Creating fake lenticular uvw1 file for grism position"
       # test if there is already a uvw1 raw or sky file before proceeding
     
       if chatter > 2: 
           print 'wheelpos ',wheelpos
	   print 'attfile  ',attfile
       wheelp1 = wheelpos
       rawfile = makewcshdr(filestub,ext,
			    attfile,
			    wheelpos=wheelp1,
			    indir=indir,
                            chatter=chatter) 
       # note that the path rawfile  = indir+'/'+filestub+'ufk_sk.img'
       tempnames.append(filestub)
       tempntags.append('fakefilestub')
   
   if lfilter_ext == None: 
       lfext = ext 
   else: 
       lfext = lfilter_ext  
   
   ffile = indir+'/'+filestub+'uw1_sk.img'
   if lfilter == 'wh'   : ffile = indir+'/'+filestub+'uwh_sk.img'
   if lfilter == 'u'    : ffile = indir+'/'+filestub+'uuu_sk.img'
   if lfilter == 'v'    : ffile = indir+'/'+filestub+'uvv_sk.img'
   if lfilter == 'b'    : ffile = indir+'/'+filestub+'ubb_sk.img'
   if lfilter == 'uvm2' : ffile = indir+'/'+filestub+'um2_sk.img'
   if lfilter == 'uvw2' : ffile = indir+'/'+filestub+'uw2_sk.img'
   if lfilter == 'fk'   : ffile = indir+'/'+filestub+'ufk_sk.img'
   
   hf = pyfits.getheader(ffile,lfext)   
   hg = pyfits.getheader(gfile,ext)

   # check for losses in grism image
   if (' BLOCLOSS' in hg):
       if float(hg['BLOCLOSS']) != 0: 
           print '#### BLOCLOSS = '+repr(hg['BLOCLOSS'])
	   msg += "BLOCLOSS=%4.1f\n"%(hg['BLOCLOSS'])
   if ('STALLOSS' in hg):
       if (float(hg['STALLOSS']) != 0): 
           print '#### STALLOSS = '+repr(hg['STALLOSS'])
	   msg += "STALLOSS=%4.1f\n"%(hg['STALLOSS'])
   if ('TOSSLOSS' in hg):
       if float(hg['TOSSLOSS']) != 0: 
           print '#### TOSSLOSS = '+repr(hg['TOSSLOSS'])
	   msg += "TOSSLOSS=%4.1f\n"%(hg['TOSSLOSS'])
   tstart = hg['TSTART']

   print 'grism exposure time = ',hg['EXPOSURE'],'  seconds'
   
   RA_PNT  = hg['RA_PNT']
   DEC_PNT = hg['DEC_PNT']
   PA_PNT  = hg['PA_PNT']   # roll angle
   time    = hg['TSTART']   # time observation
   ra_diff  = RA - RA_PNT
   dec_diff = DEC - DEC_PNT
   if ((ra_diff > 0.4) ^ (dec_diff > 0.4) ): 
       print "WARNING: the difference in the pointing from the header to the RA,DEC parameter is > 0.4 "
   RAs = repr(RA)
   DECs= repr(DEC)
   exts = repr(ext)
   lfexts = repr(lfext)

   # tbd - get random number for temp file name
   from os import getenv,system
   system('echo '+RAs+'  '+DECs+' > radec.txt ' )

   CALDB = getenv('CALDB')
   if CALDB == '': 
       print 'the CALDB environment variable has not been set'
       return None
   HEADAS = getenv('HEADAS')
   if HEADAS == '': 
       print 'The HEADAS environment variable has not been set'
       print 'That is needed for the uvot Ftools '
       return None 
   command = HEADAS+'/bin/uvotapplywcs infile=radec.txt outfile=skyfits.out wcsfile=\"'+ffile+'['+lfexts+']\" operation=WORLD_TO_PIX'
   if chatter > 0: print command
   system( command )

   f = open('skyfits.out', "r")
   line = f.read()
   if chatter > 1: print 'skyfits.out: '+line
   x1, y1 = (line.split())[2:4]
   f.close  
   system( 'echo '+repr(x1)+'  '+repr(y1)+'  > skyfits.in' )
   # 
   command = HEADAS+'/bin/uvotapplywcs infile=skyfits.in outfile=detmm.txt wcsfile=\"'+ffile+'['+lfexts+']\" operation=PIX_TO_WORLD to=D'
   if chatter > 1: print command
   system( command )
   f = open('detmm.txt', "r")
   line = f.read()
   if chatter > 1: print 'detmm: '+line
   x1, y1 = line.split()[2:4]
   f.close
   x1 = float(x1)
   y1 = float(y1)
   if chatter > 1: print " The [det]coordinates in mm are (%8.4f,%8.4f) " % ( x1, y1)
   # convert anchor in DET coordinate mm to pixels and arcsec from boresight
   anker_uvw1det = np.array([x1,y1])/0.009075+np.array((1100.5,1100.5))
   
   if (x1 < -14) | (x1 > 14) | (y1 < -14) | (y1 > 14) :
      # outside detector 
      print "/nERROR: source position is not on the detector! Aborting..."
      raise IOError("/nERROR: source position is not on the detector! ")
   
   if lfilter == "fk" : 
      l2filter = "uvw1"
   else: l2filter = lfilter   
   if wheelpos != 160:
       anker_uvw1det_offset = anker_uvw1det - np.array( boresight(filter=l2filter))  # use fixed default value boresight 
   else: 
       anker_uvw1det_offset = anker_uvw1det - np.array( boresight(filter=l2filter,date=209952100) )
   Xphi, Yphi = anker_uvw1det_offset*0.502    
   as2deg = 1./3600.    

   # cleanup
   # taken out since file is needed still:
   #   if method == 'grism_only':  os.system('rm '+filestub+'uw1_??.img ')
   if uw1rawrenamed:      os.system('mv '+uw1newraw+' '+uw1oldraw)
   if uw1skyrenamed:      os.system('mv '+uw1newsky+' '+uw1oldsky)
   
   crpix = crpix1,crpix2 = hg['crpix1'],hg['crpix2']  
   crpix = np.array(crpix)   # centre of image
   cent_ref_2img = np.array([1100.5,1100.5])-crpix  
 

   if chatter > 4:
       print 'findInputAngle. derived undistorted detector coord source in lenticular filter = (%8.5f,%8.5f)  mm '%(x1,y1)
   if chatter > 0:  
       print 'findInputAngle. derived undistorted detector coord lenticular filter           =  ',anker_uvw1det
       print 'findInputAngle. derived undistorted physical image coord lenticular filter     =  ',anker_uvw1det-cent_ref_2img
       print 'findInputAngle. derived boresight offset lenticular filter ',lfilter,' (DET pix): ',anker_uvw1det_offset
       print 'findInputAngle. derived boresight offset: (', Xphi, Yphi,') in \"  = (',Xphi*as2deg, Yphi*as2deg,') degrees'
   # cleanup temp files:   
   system('rm radec.txt skyfits.out  skyfits.in detmm.txt')
   return Xphi*as2deg, Yphi*as2deg, tstart


def get_radec(file='radec.usno', objectid=None, tool='astropy', chatter=0):
   '''Read the decimal ra,dec from a file 
   or look it up using the objectid name from CDS
      
   Parameters
   ----------
   file: str, optional
     path, filename of ascii file with just the ra, dec position in decimal degrees

   objectid : str, optional 
     name of object that is recognized by the CDS Sesame service
     if not supplied a file name is required
        
   tool : str
     name tool to use; either 'astropy' or 'cdsclient'	
	
   chatter : int
     verbosity
   
   Returns
   -------
   ra,dec : float
      Position (epoch J2000) in decimal degrees
      
   Note
   ----
   requires network service
   
   either the file present or the objectid is required   
   '''   
   if objectid == None:
     try:
        f = open(file)
        line = f.readline()
        f.close()
        ra,dec = line.split(',')
        ra  = float( ra)
        dec = float(dec)
        if chatter > 0: 
           print "reading from ",file," : ", ra,dec 
        return ra,dec
     except:
        raise IOError("Error reading ra,dec from file. Please supply an objectid or filename with the coordinates")	
   elif tool == 'cdsclient' :
      import os
      # see http://cdsarc.u-strasbg.fr/doc/sesame.htx 
      # using 'sesame' script from cdsclient package 
      # -- tbd: need to probe internet connection present or bail out ?
      command = "sesame -o2 "+objectid+" > radec.sesame"
      if chatter > 1: 
         print command
      try:	 
         if not os.system(command):
	    os.system('cat radec.sesame')
            f = open('radec.sesame')
            lines = f.readlines() 
            things = lines[1].split()
            f.close()
            command = "scat -c ub1 -ad "+things[0]+" "+things[1]+" > radec.usnofull"
            if chatter > 0: print command
            if not os.system(command):
	       f = open('radec.usnofull')
	       line = f.readline()
	       f.close()
	       if len( line.split() ) == 0:
	          if chatter > 3: print "ra,dec not found in usno-b1: returning sesame result" 
	          return float(things[0]),float(things[1])
	       ra,dec, = line.split()[1:3]
	       f = open('radec.usno','w')
	       f.write("%s,%s" % (ra,dec) )
	       f.close()
	       ra  = float( ra)
	       dec = float(dec)
               return ra,dec
	    else:
	       if chatter > 0: print 'get_radec() error call sesame '
         else:
            if chatter > 0: print "get_radec() error main call "
            return None,None	    
      except:
         raise RuntimeError("no RA and DEC were found")
   elif tool == 'astropy' :
      if objectid == None: 
         raise RuntimeError("objectid is needed for position lookup")
      from astropy import coordinates
      pos = coordinates.ICRSCoordinates.from_name(objectid)
      return pos.ra.degrees, pos.dec.degrees
   else:
      raise IOError("improper tool or file in calling parameters ")	 
	 

def get_initspectrum(net,var,fitorder, wheelpos, anchor, C_1=None,C_2=None,dist12=None, 
        xrange=None, nave = 3, predict2nd=True, chatter=0):
    """ wrapper for call 
        boxcar smooth image over -nave- pixels 
    """
    try:
       from convolve import boxcar
    except:
       from stsci.convolve import boxcar   
    return splitspectrum(boxcar(net,(nave,)),boxcar(var,(nave,)),fitorder,wheelpos,
     anchor, C_1=C_1, C_2=C_2, dist12=dist12,
     xrange=xrange,predict2nd=predict2nd, chatter=chatter)

def splitspectrum(net,var,fitorder,wheelpos,anchor,C_1=None,C_2=None,dist12=None,
         xrange=None,predict2nd=True,plotit=-790,chatter=0):
   ''' This routine will compute the counts in the spectrum 
       using the mean profiles of the orders modeled as gaussians with fixed sigma
       for each order. The counts are weighted according to the position in the 
       profile and the variance in the image (see Eq. 8, Keith Horne,1986, PASP 98, 609.)
       WARNING: No attempt is made to improve the fit of the profile to the data. 

       if the distance of the orders is less then a fraction of order width sigma, 
       the second order is estimated from the first, and the third order is neglected. 

       assumed fitorder arrays (from curved_extraction) include (first) guess spectrum.
      
       output array of counts[order, dispersion]
       
       anchor is needed to decide if the orders split up or down
       
   2010-08-21 NPMKuin (MSSL) initial code 
   2011-08-23 to do:  quality in output
   2011-09-05 mods to handle order merging
   2011-09-11 normal extraction added as well as optimal extraction for region [-sig,+sig] wide.
              larger widths violate assumption of gaussian profile. Lorentzian profile might work 
	      for more extended widths.  
                 
   '''
   from numpy import zeros,sqrt,pi,arange, array, where, isfinite, polyval, log10
   
   # the typical width of the orders as gaussian sigma [see singlegaussian()] in pixels
   sig0 = 4.8
   sig1 = 3.25
   sig2 = 4.3
   sig3 = 6.0
   
   # required order distance to run non-linear fit (about half the sigma)
   req_dist_12 = 2.0
   req_dist_13 = 2.0
   req_dist_23 = 2.0
   
   # factor to account for reduction in variance due to resampling/rotation
   varFudgeFactor = 0.5
   
   # approximate width of extended spectral feature in a line profile (in pix) poly 
   # width = polyval(widthcoef, lambda)  ; while the main peak ~ 3 pix (~sigma)
   widthcoef = array([-8.919e-11,2.637e-06,-1.168e-02,15.2])
   
   # extract simple sum to n x sigma
   nxsig = 1.0
   
   # set amplitude limits second order
   amp2lim = None
   
   top = True
   if (anchor[0] < 1400) & (anchor[1] < 800) : top = False
   
   try:
      (present0,present1,present2,present3),(q0,q1,q2,q3), \
      (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
      (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
      (x,xstart,xend,sp_all,quality)  = fitorder
      x0 = x1 = x2 = x3 = x 
   except RuntimeError:
     print "get_cuspectrum: input parameter fitorder is not right\n ABORTING . . . "
     raise RuntimeError
     return
     
   nx = len(x0)  
   x0 = x0[q0]
   x1 = x1[q1]
   x2 = x2[q2]
   x3 = x3[q3]  
     
   # check that the dimension size is right
   if nx != net.shape[1]:
     print "get_cuspectrum: size of input image %4i and fitorder %4i not compatible "%(nx,net.shape[1])
     raise RuntimeError
     return 
     
   # force var to be positive; assume var is in counts/pix  
   q = where(var <= 0)
   var[q] = 1.e-10
   
   # initialize
   counts     = zeros(nx*4).reshape(4,nx)
   variance   = zeros(nx*4).reshape(4,nx)
   borderup   = zeros(nx*4).reshape(4,nx) - 99
   borderdown = zeros(nx*4).reshape(4,nx) - 99 
   newsigmas     = zeros(nx*4).reshape(4,nx)
   
   bs = 1.0 # borderoffset in sigma for plot
   qflag = quality_flags()
  
   # here counts[0,:] = zeroth order
   #      counts[1,:] = first order
   # etc. for 2nd, 3rd orders.
   
   fractions  = zeros(nx*4).reshape(4,nx) -1
   count_opt  = zeros(nx*4).reshape(4,nx) 
   var_opt    = zeros(nx*4).reshape(4,nx) 
    
   # predict the second order amplitude
   
   if (predict2nd & present2 & (sp_first[q2].mean() > 0.0) & (C_1 != None) & (C_2 != None)):
      # dis = q1[0]
      # spnet = sp_first[q1[0]]
      # qual = quality[q1[0]] 
      # dismin = dlim1L
      # dismax = dlim1U
      #  (wav2, dis2, flux2, qual2, d12), (wave, dis, spnet) = predict_second_order(dis,spnet,C_1,C_2,d12,qual,dismin,dismax,wheelpos)
      
      SO = predict_second_order(x[q1[0]], sp_first[q1[0]], C_1,C_2,dist12,quality[q1[0]], dlim1L,dlim1U,wheelpos)
      dis2 = (SO[1][1]+dist12)


   if xrange == None: 
      ileft = 2
      irite = nx -2
   else:
      ileft = xrang[0]
      irite = xrang[1]	            
        
   for i in range(ileft,irite):
      #if i in q3[0]: 
      #   ans = raw_input('continue?')
      #	  chatter = 5
	 
      if chatter > 3: print "get_initspectrum.curved_extraction [trackfull] fitting i = %2i x=%6.2f"%(i,x[i])

         # do/try the zeroth order 
	 
      if i in q0[0]: 
         if chatter > 4: print " zeroth order"
	 # normalization factor for singlegaussian is sqrt(pi).sigma.amplitude 
	 # but use the measured counts within 3 sigma.
	 sig0 = polyval(sig0coef, i)
	 j1 = int(y0[i] - nxsig*sig0)
	 j2 = int(y0[i] + nxsig*sig0 + 1)
	 # get weighted sum now. Renormalize to get total counts in norm.
	 yr = arange(j1,j2)
	 prob = singlegaussian(yr,1.0,y0[i],sig0)
	 P = (prob/prob.sum()).flatten()
	 V = var[j1:j2,i].flatten()*varFudgeFactor
	 net0 = net[j1:j2,i].flatten()
	 net0[net0 < 0.] = 0.
	 qfin = isfinite(net0)

	 variance[0,i] = (V[qfin]).sum()
	 counts[0,i] = net0[qfin].sum() 
	 
	 # optimal extraction
	 j1 = int(y0[i] - sig0)
	 j2 = int(y0[i] + sig0)
	 yr = arange(j1,j2)
	 prob = singlegaussian(yr,1.0,y0[i],sig0)
	 P = (prob/prob.sum()).flatten()
	 V = var[j1:j2,i].flatten()*varFudgeFactor
	 net0 = net[j1:j2,i].flatten()
	 net0[net0 < 0.] = 0.
	 qfin = isfinite(net0)
	 var_opt[0,i]   = 1.0/ (( P[qfin]*P[qfin]/V[qfin]).sum())
	 count_opt[0,i] = var_opt[0,i] * ( P[qfin] * net0[qfin] / V[qfin] ).sum()
	 newsigmas[0,i] = sig0
	 borderup  [0,i] = y0[i] - bs*sig0
	 borderdown[0,i] = y0[i] + bs*sig0

         

         # do the first order  
	 
      if ((i in q1[0]) & (i not in q2[0])) :
         if chatter > 4: print " first order"
	 sig1 = polyval(sig1coef,i) 
	 j1 = int(y1[i] - nxsig*sig1)
	 j2 = int(y1[i] + nxsig*sig1 + 1)

	 Xpos = array([i])
	 Ypos = array(y1[i])
	 sigmas = array([sig1])
	 Z = get_components(Xpos,net,Ypos,wheelpos,chatter=chatter,\
	        composite_fit=True,caldefault=True,sigmas=sigmas,
		fiterrors=False,fixsig=True,fixpos=True,amp2lim=None)
	 a1   = Z[0][0][0]	
         sig1 = Z[0][0][2]

	 # get weighted sum now. Renormalize to get total counts in norm.
	 yr = arange(j1,j2)
	 prob = singlegaussian(yr,1.0,y1[i],sig1)
	 P = (prob/prob.sum()).flatten()
	 V = var[j1:j2,i].flatten()*varFudgeFactor
	 net1 = net[j1:j2,i].flatten()
	 net1[net1 < 0.] = 0.
	 qfin = isfinite(net1)
	 counts[1,i] = net1[qfin].sum()
	 variance[1,i] = (V[qfin]).sum()
	 
	 # optimal extraction 
	 j1 = int(y1[i] - sig1)
	 j2 = int(y1[i] + sig1 + 1)
	 # get weighted sum now. Renormalize to get total counts in norm.
	 yr = arange(j1,j2)
	 prob = singlegaussian(yr,1.0,y1[i],sig1)
	 P = (prob/prob.sum()).flatten()
	 V = var[j1:j2,i].flatten()*varFudgeFactor
	 net1 = net[j1:j2,i].flatten()
	 net1[net1 < 0.] = 0.
	 qfin = isfinite(net1)
	 var_opt[1,i]   = 1.0/ (( P[qfin]*P[qfin]/V[qfin]).sum())
	 count_opt[1,i] = var_opt[1,i] * ( P[qfin] * net1[qfin] / V[qfin] ).sum()
         newsigmas    [1,i] = sig1
	 borderup  [1,i] = y1[i] - bs*sig1
	 borderdown[1,i] = y1[i] + bs*sig1
         fractions [1,i] = 1.
	    

      # do the first and second order  
	 
      if ((i in q1[0]) & (i in q2[0]) & (i not in q3[0])):
         if chatter > 4: print " first and second orders"
	 sig1 = polyval(sig1coef,i)
	 sig2 = polyval(sig2coef,i)
	 
	 if abs(y2[i]-y1[i]) < req_dist_12:
	    # do not fit profiles; use predicted second order 
	    
	    # first order fit
	    Xpos = array([i])
	    if top:
               j1 = int(y1[i] - nxsig*sig1)
	       j2 = int(y2[i] + nxsig*sig2 + 1)
	       Ypos = array([y1[i]])
	       sigmas = array([sig1])
            else:
	       j1 = int(y2[i] - nxsig * sig2)
	       j2 = int(y1[i] + nxsig * sig1)
	       Ypos = array([y1[i]])
               sigmas = array([sig1])
	 
	    Z = get_components(Xpos,net,Ypos,wheelpos,chatter=chatter,\
	        composite_fit=True,caldefault=True,sigmas=sigmas,
		fixsig=True,fixpos=True,fiterrors=False)
	    
	    
 	    a1 = Z[0][0][2] 
	    sig1 = Z[0][0][4]
	    
	    quality[i] += qflag['overlap']
	    
            # find second order prediction min, max -> amp2lim
            
            ilo = dis2.searchsorted(i)
	    a2 = SO[1][3][ilo-1:ilo+1].mean()
	    
	    if a1 > a2: 
	       a1 -= a2
	    else: a1 = 0.   
	 	 
	 else:
	    # orders 1,2 separated enough to fit profiles
	    if top:
               j1 = int(y1[i] - nxsig*sig1)
	       j2 = int(y2[i] + nxsig*sig2 + 1)
	       Ypos = array([y1[i],y2[i]])
	       sigmas = array([sig1,sig2])
            else:
	       j1 = int(y2[i] - nxsig * sig2)
	       j2 = int(y1[i] + nxsig * sig1)
	       Ypos = array([y2[i],y1[i]])
               sigmas = array([sig2,sig1])
	      
	    # fit for the amplitudes of first and second order
	    Xpos = array([i])
	 
	    Z = get_components(Xpos,net,Ypos,wheelpos,chatter=chatter,\
	        composite_fit=True,caldefault=True,sigmas=sigmas,
		fiterrors=False,fixsig=True,fixpos=True,amp2lim=amp2lim)
		
	    # amplitudes of first and second order determine the flux ratio	 	
	    if top:
 	       a1 = Z[0][0][0] 
 	       a2 = Z[0][0][3]
	       sig1 = Z[0][0][2]
	       sig2 = Z[0][0][5] 
            else:
 	       a2 = Z[0][0][0] 
 	       a1 = Z[0][0][3] 
	       sig2 = Z[0][0][2]
	       sig1 = Z[0][0][5] 
	    if a1 <= 0. : a1 = 1.e-6  
	    if a2 <= 0. : a2 = 1.e-7  
	 
	    if chatter > 4: 
	       print 'get_initspectrum: i=%5i a1=%6.1f   a2=%6.1f  y1=%6.1f  y2=%6.1f ' % (i,a1,a2,y1[i],y2[i])
	 
	 yr   = arange( max([int(y1[i]-3.*sig1),0]) , min([int(y2[i]+3.*sig1),200]) ) # base 1 pixels
	 ff1 = singlegaussian(yr,a1,y1[i],sig1)
	 ff2 = singlegaussian(yr,a2,y2[i],sig2)  
	 fft = ff1+ff2    # total
	 frac1 = ff1/fft  # fraction of counts belonging to first order for each pixel
	 frac2 = ff2/fft  # fractional contribution of other order to counts 
	                     #   normalised by total for each pixel  (= divide by ff1t)
	 Var = var[yr,i] * varFudgeFactor
	 P1 = (ff1/fft.sum()).flatten()  # probability normalised fraction per pixel
	 net1 = net[yr ,i].flatten() * frac1  # counts that belong to first order
	 net1[net1 < 0.] = 0.
	 qfin = isfinite(net1)
	 net1_tot = net1[qfin].sum()
	 V1 = Var * (1.+ frac2)   # variance of pixel - add other order as noise source
	 	 
	 counts[1,i] = net1_tot
	 # compute a simple weighted pixel-by-pixel variance, and add it. Weight by normalized net counts/pixel.
	 variance[1,i] = (V1[qfin]).sum()

	 P2 = (ff2/fft.sum()).flatten()
	 V2 = Var * (1.+ frac1) 
	 net2 = net[yr ,i].flatten() * frac2
	 net2[net2 < 0.] = 0.
	 qfin = isfinite(net2)
	 net2_tot = net2[qfin].sum()

	 counts[2,i] = net2_tot	
	 variance[2,i] = (V2[qfin]).sum()

         fractions [1,i] = frac1.sum()
         fractions [2,i] = frac2.sum()
	 
	 # optimal extraction order 1
	 yr1   = arange( max([0,int(y1[i]-sig1)]) , min([int(y1[i]+sig1),200]) ) # base 1 pixels
	 Var = var[yr1,i] * varFudgeFactor
	 ff1 = singlegaussian(yr1,a1,y1[i],sig1)
	 ff2 = singlegaussian(yr1,a2,y2[i],sig2)  
	 fft = ff1+ff2    # total
	 frac1 = ff1/fft  # fraction of counts belonging to first order for each pixel
	 frac2 = ff2/fft  # fractional contribution of other order to counts 
	                     #   normalised by total for each pixel  (= divide by ff1t)
	 P1 = (ff1/fft.sum()).flatten()  # probability normalised fraction per pixel
	 net1 = net[yr1 ,i].flatten() * frac1  # counts that belong to first order
	 net1[net1 < 0.] = 0.
	 qfin = isfinite(net1)
	 net1_tot = net1[qfin].sum()
	 V1 = Var * (1.+ frac2)   # variance of pixel - add other order as noise source
	 var_opt[1,i]   = 1.0/ (( P1[qfin]*P1[qfin]/V1[qfin]).sum())
	 count_opt[1,i] = var_opt[1,i] * ( P1[qfin] * net1[qfin] / V1[qfin] ).sum()
	 newsigmas[1,i] = sig1
	     
	 yr2   = arange( max([0,int(y2[i]-sig2)]) , min([int(y2[i]+sig2),200]) ) # base 1 pixels
	 Var = var[yr2,i] * varFudgeFactor
	 ff1 = singlegaussian(yr2,a1,y1[i],sig1)
	 ff2 = singlegaussian(yr2,a2,y2[i],sig2)  
	 fft = ff1+ff2    # total
	 frac1 = ff1/fft  # fraction of counts belonging to first order for each pixel
	 frac2 = ff2/fft  # fractional contribution of other order to counts 
	                     #   normalised by total for each pixel  (= divide by ff1t)
	 P2 = (ff2/fft.sum()).flatten()
	 V2 = Var * (1.+ frac1) 
	 net2 = net[yr2 ,i].flatten() * frac2
	 net2[net2 < 0.] = 0.
	 qfin = isfinite(net2)
	 net2_tot = net2[qfin].sum()
	 var_opt[2,i]   = 1.0/ (( P2[qfin]*P2[qfin]/V2[qfin]).sum())
	 count_opt[2,i] = var_opt[2,i] * ( P2[qfin] * net2[qfin] / V2[qfin] ).sum()
         newsigmas[2,i] = sig2
	 
	 borderup  [1,i] = y1[i] - bs*sig1
	 borderdown[1,i] = y1[i] + bs*sig1
	 borderup  [2,i] = y2[i] - bs*sig2
	 borderdown[2,i] = y2[i] + bs*sig2


	 if ((plotit > 0) & (i >= plotit)):
            from pylab import plot, legend, figure, clf,title,text
	    print Z[0]
	    print '*********************'
	    print qfin
	    print net1
	    print counts[1,i],count_opt[1,i],variance[2,i],var_opt[2,i]
	    figure(11) ; clf()
	    plot(yr,net[yr,i],'y',lw=2)
	    plot(yr,ff1,'k')
	    plot(yr,ff2,'r')
	    plot(yr,net1/P1,'bv')
	    plot(yr,net2/P2,'c^',alpha=0.7)
	    legend(['net','ff1','ff2','net1/P1','net2/P2'])
	    title("%7.1e %6.1f %4.1f %7.1e %6.1f %4.1f"%(a1,y1[i],sig1,a2,y2[i],sig2))
	    figure(12) ; clf()
	    plot(yr,P1,'k')
	    plot(yr,P2,'r')
	    plot(yr,frac1,'b')
	    plot(yr,frac2,'m') 		     
	    legend(['P1','P2','frac1','frac2'])	    
	    
	    gogo = raw_input('continue?')
	              	    
      # do the first, second and third order case  
      
      if ((i in q1[0]) & (i in q2[0]) & (i in q3[0])):
            if chatter > 4: print "first, second and third order"
	    sig1 = polyval(sig1coef,i)
	    sig2 = polyval(sig2coef,i)
	    sig3 = polyval(sig3coef,i)
	    
	    if ((abs(y2[i]-y1[i]) < req_dist_12) & (abs(y3[i]-y1[i]) < req_dist_13)):
	       # do not fit profiles; use only predicted second order 
	    
	       # first order fit
	       Xpos = array([i])
	       if top:
                  j1 = int(y1[i] - nxsig*sig1)
	          j2 = int(y2[i] + nxsig*sig2 + 1)
	          Ypos = array([y1[i]])
	          sigmas = array([sig1])
               else:
	          j1 = int(y2[i] - nxsig * sig2)
	          j2 = int(y1[i] + nxsig * sig1)
	          Ypos = array([y1[i]])
                  sigmas = array([sig1])
	 
	       Z = get_components(Xpos,net,Ypos,wheelpos,chatter=chatter,\
	        composite_fit=True,caldefault=True,sigmas=sigmas,
		fiterrors=False,fixsig=True,fixpos=True)
	    
 	       #a1 = Z[0][0][2]
	       #sig1 = Z[0][0][4] 
	       a1 = Z[0][0][0]
	       sig1 = Z[0][0][2]
	    
               # find second order prediction min, max -> amp2lim
            
               ilo = dis2.searchsorted(i)
	       a2 = SO[1][2][ilo-1:ilo+1].mean()
	    
	       if a1 > a2: 
	          a1 -= a2
	       else: a1 = 0.   

               a3 = 0.
	       
	       quality[i] += qflag['overlap']

	    else:
	       if top:
                  j1 = int(y1[i] - nxsig*sig1)
	          j2 = int(y3[i] + nxsig*sig3 + 1)
	          Ypos = array([y1[i],y2[i],y3[i]])
	          sigmas = array([sig1,sig2,sig3])
               else:
	          j1 = int(y3[i] - nxsig*sig3)
	          j2 = int(y1[i] + nxsig*sig1)
	          Ypos = array([y3[i],y2[i],y1[i]])
                  sigmas = array([sig3,sig2,sig1])
		  
	       # fit for the amplitudes of first and second order
	       Xpos = array([i])
	    
	       Z = get_components(Xpos,net,Ypos,wheelpos,chatter=chatter,\
	           composite_fit=True,caldefault=True,sigmas=sigmas,
		   fiterrors=False,amp2lim=amp2lim,fixsig=True,fixpos=True)
		
	       if top:
 	          a1 = Z[0][0][0] 
 	          a2 = Z[0][0][3] 
 	          a3 = Z[0][0][6] 
 	          sig1 = Z[0][0][2] 
 	          sig2 = Z[0][0][5] 
 	          sig3 = Z[0][0][8] 
               else:
 	          a1 = Z[0][0][6] 
 	          a2 = Z[0][0][3] 
 	          a3 = Z[0][0][0] 
 	          sig1 = Z[0][0][8] 
 	          sig2 = Z[0][0][5] 
 	          sig3 = Z[0][0][2] 

            yr1 = arange(int( y1[i]-nxsig*sig1) , int(y1[i]+nxsig*sig1) )
	    ff1 =     singlegaussian(yr1,a1,y1[i],sig1)
	    ff1t = ff1+singlegaussian(yr1,a2,y2[i],sig2)+singlegaussian(yr1,a3,y3[i],sig3)
	    frac1 = ff1/ff1t 
	       
	    yr2 = arange( int(y2[i]-nxsig*sig2) , int(y2[i]+nxsig*sig2) )
	    ff2 = singlegaussian(yr2,a2,y2[i],sig2) 
	    ff2t = ff2 + singlegaussian(yr2,a1,y1[i],sig1) + singlegaussian(yr2,a3,y3[i],sig3)
	    frac2 = ff2/ff2t
	       
	    yr3 = arange( int(y3[i]-nxsig*sig3 ),int( y3[i]+nxsig*sig3 ))
	    ff3 = singlegaussian(yr3,a3,y3[i],sig3)
	    ff3t = ff3+singlegaussian(yr3,a1,y1[i],sig1)+singlegaussian(yr3,a2,y2[i],sig2)
	    frac3 = ff3/ff3t
	       
	    fra21 = singlegaussian(yr2,a1,y1[i],sig1)
	    fra21 /= (fra21+singlegaussian(yr2,a2,y2[i],sig2)+singlegaussian(yr2,a3,y3[i],sig3))
	    fra31 = singlegaussian(yr3,a1,y1[i],sig1)
	    fra31 /= (fra31+singlegaussian(yr3,a2,y2[i],sig2)+singlegaussian(yr3,a3,y3[i],sig3))
	       
	    fra12 = singlegaussian(yr1,a2,y2[i],sig2) 
	    fra12 /= (fra12+singlegaussian(yr1,a1,y1[i],sig1) + singlegaussian(yr1,a3,y3[i],sig3))
	    fra32 = singlegaussian(yr3,a2,y2[i],sig2) 
	    fra32 /= (fra32+singlegaussian(yr3,a1,y1[i],sig1) + singlegaussian(yr3,a3,y3[i],sig3))
	       
	    fra13 = singlegaussian(yr1,a3,y3[i],sig3)
	    fra13 /= (fra13+singlegaussian(yr1,a1,y1[i],sig1)+singlegaussian(yr1,a2,y2[i],sig2))
	    fra23 = singlegaussian(yr2,a3,y3[i],sig3)
	    fra23 /= (fra23+singlegaussian(yr2,a1,y1[i],sig1)+singlegaussian(yr2,a2,y2[i],sig2))
	       
	    Var1 = var[yr1,i].flatten()* varFudgeFactor
	    Var2 = var[yr2,i].flatten()* varFudgeFactor
	    Var3 = var[yr3,i].flatten()* varFudgeFactor

	    P1 = (ff1/ff1.sum()).flatten()  # probability of first order photon 
	    P2 = (ff2/ff2.sum()).flatten()
	    P3 = (ff3/ff3.sum()).flatten()
	    V1 = Var1 * (1.+ fra12+fra13) # variance of pixel 
	    V2 = Var2 * (1.+ fra21+fra23) 
	    V3 = Var3 * (1.+ fra31+fra32) 
	    net1 = net[yr1 ,i].flatten() * frac1  # counts that belong to first order
	    net2 = net[yr2 ,i].flatten() * frac2
	    net3 = net[yr3 ,i].flatten() * frac3	       
	    net1[ net1 < 0.] = 0.
	    net2[ net2 < 0.] = 0.
	    net3[ net3 < 0.] = 0.
            qfin1 = isfinite(net1)
	    qfin2 = isfinite(net2)
	    qfin3 = isfinite(net3)
	    counts[1,i] = net1[qfin1].sum()
	    counts[2,i] = net2[qfin2].sum()	
	    counts[3,i] = net3[qfin3].sum()	
	    variance[1,i] = (V1[qfin1]).sum()
	    variance[2,i] = (V2[qfin2]).sum()
	    variance[3,i] = (V3[qfin3]).sum()
	    
	    borderup  [1,i] = y1[i] - bs*sig1
	    borderdown[1,i] = y1[i] + bs*sig1
	    borderup  [2,i] = y2[i] - bs*sig2
	    borderdown[2,i] = y2[i] + bs*sig2
	    borderup  [3,i] = y3[i] - bs*sig3
	    borderdown[3,i] = y3[i] + bs*sig3
            fractions [1,i] = frac1.sum()
            fractions [2,i] = frac2.sum()
            fractions [3,i] = frac3.sum()

            # optimal extraction
	    
            yr1 = arange(int( y1[i]-sig1) , int(y1[i]+sig1) )
	    ff1 =     singlegaussian(yr1,a1,y1[i],sig1)
	    ff1t = ff1+singlegaussian(yr1,a2,y2[i],sig2)+singlegaussian(yr1,a3,y3[i],sig3)
	    frac1 = ff1/ff1t 
	       
	    yr2 = arange( int(y2[i]-sig2) , int(y2[i]+sig2) )
	    ff2 = singlegaussian(yr2,a2,y2[i],sig2) 
	    ff2t = ff2 + singlegaussian(yr2,a1,y1[i],sig1) + singlegaussian(yr2,a3,y3[i],sig3)
	    frac2 = ff2/ff2t
	       
	    yr3 = arange( int(y3[i]-sig3 ),int( y3[i]+sig3 ))
	    ff3 = singlegaussian(yr3,a3,y3[i],sig3)
	    ff3t = ff3+singlegaussian(yr3,a1,y1[i],sig1)+singlegaussian(yr3,a2,y2[i],sig2)
	    frac3 = ff3/ff3t
	       
	    fra21 = singlegaussian(yr2,a1,y1[i],sig1)
	    fra21 /= (fra21+singlegaussian(yr2,a2,y2[i],sig2)+singlegaussian(yr2,a3,y3[i],sig3))
	    fra31 = singlegaussian(yr3,a1,y1[i],sig1)
	    fra31 /= (fra31+singlegaussian(yr3,a2,y2[i],sig2)+singlegaussian(yr3,a3,y3[i],sig3))
	       
	    fra12 = singlegaussian(yr1,a2,y2[i],sig2) 
	    fra12 /= (fra12+singlegaussian(yr1,a1,y1[i],sig1) + singlegaussian(yr1,a3,y3[i],sig3))
	    fra32 = singlegaussian(yr3,a2,y2[i],sig2) 
	    fra32 /= (fra32+singlegaussian(yr3,a1,y1[i],sig1) + singlegaussian(yr3,a3,y3[i],sig3))
	       
	    fra13 = singlegaussian(yr1,a3,y3[i],sig3)
	    fra13 /= (fra13+singlegaussian(yr1,a1,y1[i],sig1)+singlegaussian(yr1,a2,y2[i],sig2))
	    fra23 = singlegaussian(yr2,a3,y3[i],sig3)
	    fra23 /= (fra23+singlegaussian(yr2,a1,y1[i],sig1)+singlegaussian(yr2,a2,y2[i],sig2))
	       
	    Var1 = var[yr1,i].flatten()* varFudgeFactor
	    Var2 = var[yr2,i].flatten()* varFudgeFactor
	    Var3 = var[yr3,i].flatten()* varFudgeFactor

	    P1 = (ff1/ff1.sum()).flatten()  # probability of first order photon 
	    P2 = (ff2/ff2.sum()).flatten()
	    P3 = (ff3/ff3.sum()).flatten()
	    V1 = Var1 * (1.+ fra12+fra13) # variance of pixel 
	    V2 = Var2 * (1.+ fra21+fra23) 
	    V3 = Var3 * (1.+ fra31+fra32) 
	    net1 = net[yr1 ,i].flatten() * frac1  # counts that belong to first order
	    net2 = net[yr2 ,i].flatten() * frac2
	    net3 = net[yr3 ,i].flatten() * frac3	       
	    net1[ net1 < 0.] = 0.
	    net2[ net2 < 0.] = 0.
	    net3[ net3 < 0.] = 0.
            qfin1 = isfinite(net1)
	    qfin2 = isfinite(net2)
	    qfin3 = isfinite(net3)
	    var_opt[1,i]   = 1.0/ (( P1[qfin1]*P1[qfin1]/V1[qfin1]).sum())
	    count_opt[1,i] = var_opt[1,i] * ( P1[qfin1] * net1[qfin1] / V1[qfin1] ).sum()
	    newsigmas[1,i] = sig1
	    var_opt[2,i]   = 1.0/ (( P2[qfin2]*P2[qfin2]/V2[qfin2]).sum())
	    count_opt[2,i] = var_opt[2,i] * ( P2[qfin2] * net2[qfin2] / V2[qfin2] ).sum()
	    newsigmas[2,i] = sig2
	    var_opt[3,i]   = 1.0/ (( P3[qfin3]*P3[qfin3]/V3[qfin3]).sum())
	    count_opt[3,i] = var_opt[3,i] * ( P3[qfin3] * net3[qfin3] / V3[qfin3] ).sum() 
	    newsigmas[3,i] = sig3

   return count_opt, var_opt, borderup, borderdown, (fractions,counts, variance, newsigmas) 


  
def updateFitorder(extimg, fitorder1, wheelpos, predict2nd=False, fit_second=False, \
    fit_third=False, C_1=None, C_2=None, d12=None, full=False,  chatter=0):
   ''' 
   
   2011-08-26 NPMKuin (MSSL/UCL) fine-tune the parameters determining 
   the overall profile of the orders, especially the position of the 
   centre and the width by fitting gaussians to a limited number of bands.
   
   Return an updated fitorder array, and new background. Won't work when 
   the orders overlap too much. (TBD what exactly is -too much-)
   
   Use the predicted second order if predict@nd is set - requires C_1, C_2, d12
   
   2012-01-05 NPMK   
   '''
   from numpy import zeros,sqrt,pi,arange, array, where, isfinite,linspace
   import numpy as np
   
   # the typical width of the orders as gaussian sigma in pixels
   sig0 = 4.8
   sig1 = 3.25
   sig2 = 4.3
   sig3 = 4.9
      
   try:  (present0,present1,present2,present3),(q0,q1,q2,q3), \
      (y0,dlim0L,dlim0U,sig0coef,sp_zeroth),(y1,dlim1L,dlim1U,sig1coef,sp_first),\
      (y2,dlim2L,dlim2U,sig2coef,sp_second),(y3,dlim3L,dlim3U,sig3coef,sp_third),\
      (x,xstart,xend,sp_all,quality)  = fitorder1

   except RuntimeError:
     print "updateFitorder: input parameter fitorder is not right\n ABORTING . . . "
     raise RuntimeError
     return
     
   fsig0coef = array([4.2]) 
   nx = len(x)  
   amp2lim = None # default
      
   # check that the dimension size is right
   if nx != extimg.shape[1]:
     print "spectrumProfile: size of input image %4i and fitorder %4i not compatible "%(nx,extimg.shape[1])
     raise RuntimeError
     return 

   oldpres2, oldpres3 = present2, present3
     
   # do not update third order when it is too short or fit_second false
   if present3 & ((abs(dlim3U-dlim3L) < 100) | (not fit_second) | (not fit_third)):
      present3 = False  
      if chatter > 2:
         print "third order update curvature disabled: not enough points"
      
   # do not update second order when it is too short
   if present2 & ((abs(dlim2U-dlim2L) < 100) | (not fit_second)) :
      if chatter > 2:
         print "second order update curvature disabled: not enough points"
      present2 = False   
          
   # define some list to tuck the newly fitted parameters into
   fx0=list() ; fx1=list() ; fx2=list() ; fx3=list()    # position along dispersion direction
   fy0=list() ; fy1=list() ; fy2=list() ; fy3=list()    # position normal to dispersion direction
   bg0=list() ; bg1=list() ; e_bg0=list() ; e_bg1=list()
   fsig0=list(); fsig1=list(); fsig2=list(); fsig3=list()         # sigma 
   e_fx0=list() ; e_fx1=list() ; e_fx2=list() ;e_fx3=list()      # errors
   e_fy0=list() ; e_fy1=list() ; e_fy2=list() ; e_fy3=list()      # errors
   e_fsig0=list(); e_fsig1=list(); e_fsig2=list(); e_fsig3=list()   # errors
      
   #   Fit the orders with gaussians based on the approximate positions to get 
   #   a trusted solution for the position of the orders and the sigmas of the 
   #   orders. 

   # do the zeroth order
   xpos = arange(30)
   
   if present0:
      for i in range(q0[0][0]+15,q0[0][-1],30):
         if chatter > 4: print " refit zeroth order position and sigma"
      
         # only fit high quality 
         q = where(quality[i-15:i+15] == 0)[0] + (i-15) 
         Z = get_components(xpos,extimg[:,i-15:i+15],y0[i],wheelpos,chatter=chatter,\
	           composite_fit=True,caldefault=True,sigmas=None)   
		   
         (params,e_params,flag),input = Z	   	    
         status = flag[5]  	    
         # here [bg0,bg1,a0,p0,sig0] = params
         # here [e_bg0,e_bg1,e_a0,e_p0,e_sig0] = e_params
	 if status > 0:
            fx0.append( x[i] )
            fy0.append( params[3] )
            fsig0.append( params[4] )
            e_fx0.append( 15 )
            e_fy0.append( e_params[3] )
            e_fsig0.append( e_params[4] )
            bg0.append(params[0])
            bg1.append(params[1])
            e_bg0.append(e_params[0])
            e_bg1.append(e_params[1])
         elif chatter > 1:
            print 'updateFitorder zeroth order failure fit: ' 
	    print 'INPUT  i: ',i,',   xpos : ',xpos,'   ypos : ',y0[i]
	    print 'params   : ',params
	    print 'e_params : ',e_params	 

      fx0q = np.isfinite(np.array(fx0)) & np.isfinite(np.array(fy0))

      if len(fx0) > 0:
      # re-fit the zeroth order y-offset  (remove bad points ???)
         fcoef0 = np.polyfit(np.array(fx0)[fx0q],np.array(fy0)[fx0q]-100.,2)
         fsig0coef = np.polyfit(np.array(fx0)[fx0q],np.array(fsig0)[fx0q],2)
      else:
         if chatter > 1: print "updateFitorder: no success refitting zeroth order"
         fcoef0 = array([-0.07,-49.])
         fsigcoef0 = sig0coef      	 
   else:
      fcoef0 = array([-0.07,-49.])
      fsig0coef = sig0coef
      
   #     positions in first order (no second / third order to fit) 
   
   # implied present1
         
   if chatter > 4: 
      print "updateFitorder: refit first order position and sigma"
      print "updateFitorder: centre bins ",range(q1[0][0]+15,q2[0][0],30)
   
	
   if present2: 
      uprange1 = q2[0][0]
   else: 
      uprange1 = q1[0][-1]
   
   for i in range(q1[0][0]+15,uprange1,30):
      if chatter > 4:  print  "bin: ",i,"  x[i] = ",x[i]
	 
      # only fit high quality 
      q = where(quality[i-15:i+15] == 0)[0] + (i-15) 
      
      Z = get_components(xpos,extimg[:,i-15:i+15],y1[i],wheelpos,chatter=chatter,\
	        composite_fit=True,caldefault=True,sigmas=None)   
		
      (params,e_params,flag),input = Z	   
      status = flag[5]  	    
      if chatter > 4:
         print "updateFitorder: 1st, status = ",flag
	 print "params = ",params
	 print "errors = ",e_params	    
      # here [bg0,bg1,a1,p1,sig1] = params
      # here [e_bg0,e_bg1,e_a1,e_p1,e_sig1] = e_params
      if status > 0:
         fx1.append( x[i] )
         fy1.append( params[3] )
	 fsig1.append( params[4] )
         e_fx1.append( 15 )
         e_fy1.append( e_params[3] )
         e_fsig1.append( e_params[4] )
         bg0.append(params[0])
         bg1.append(params[1])
         e_bg0.append(e_params[0])
         e_bg1.append(e_params[1])
      elif chatter > 1:
         print 'updateFitorder 1st order failure fit: ' 
	 print 'INPUT  i: ',i,',   xpos : ',xpos,'   ypos : ',y1[i]
	 print 'params   : ',params
	 print 'e_params : ',e_params	 

    
   # predict the second order amplitude
   
   if (predict2nd & present2 & (C_1 != None) & (C_2 != None) & (d12 != None)):
      print "updateFitorder: calling predict_second_order()"
      # here the arguments are:	dis = q1[0]
      # 			spnet = sp_first[q1[0]]
      # 			qual = quality[q1[0]]      ? or ... x[q1[0]] argument? 
      # 			dismin = dlim1L
      # 			dismax = dlim1U
      #  (wav2, dis2, flux2, qual2, d12), (wave, dis, spnet) = predict_second_order(dis,spnet,C_1,C_2,d12,qual,dismin,dismax,wheelpos)
      SO = predict_second_order(x[q1[0]], sp_first[q1[0]], C_1, C_2, d12, quality[q1[0]], dlim1L,dlim1U,wheelpos)
      dis2 = (SO[0][1]+d12)
      flx2 = SO[0][2]
      sq = isfinite(dis2+flx2)
      #dis2 = dis2[sq]
      flx2 = flx2[sq]
   else:
      print "updateFitorder: skipped call to predict_second_order()"   

       
   #     positions in first and second orders before third order appears
   if present2: 
      
      if present3: uprange2 = q3[0][0]
      else: uprange2 = q2[0][-1]
      
      if chatter > 4: 
         print "updateFitorder: refit first + second order position and sigma"
         print "updateFitorder: centre bins ",range(q2[0][0]+15,uprange2,30)
	 
      for i in range(q2[0][0]+15,uprange2,30):
   
         if chatter > 4:  print  "bin: ",i,"  x[i] = ",x[i]
	 
         # only fit high quality 
         q = where(quality[i-15:i+15] == 0)[0] + (i-15) 
      
         # use the predicted second order to define limits to the amplitude for fitting
	 
         if isfinite(y2[i]) & isfinite(y1[i]):
            if ( (abs(y2[i]-y1[i]) < 5) & (abs(y2[i]-y1[i]) >= 1.5) ): 
               # find second order prediction for this range, min, max -> amp2lim
	       if predict2nd: 
                  if dis2[0] <= i-15:
                     ilo = dis2.searchsorted(i-15)
                  else: ilo=0
	       
                  if dis2[-1] > i+15: 	 
                    iup = dis2.searchsorted(i+15)+1
                  else: iup = dis2[-1]
	    
	          if chatter > 4: 
		     print "ilo:iup = ",ilo,iup
		     print " min: ",np.min(flx2)
		     print " max: ",np.max(flx2)
                  amp2lim = array([np.min(flx2),np.max(flx2)])
	       
	       else:
	          print "Error: need to predict 2nd order"
	  	  amp2lim=None    
            elif ( abs(y2[i]-y1[i]) < 1.5 ): 
               if predict2nd:
                  # find second order prediction for this range,but restrict range min, max -> amp2lim
                  if dis2[0] <= i-15:
                     ilo = dis2.searchsorted(i-15)
                  else: ilo=0
	      
                  if dis2[-1] > i+15: 	 
                     iup = dis2.searchsorted(i+15)+1
                  else: iup = dis2[-1]
	      
	          
		  amp2range = abs(np.min(flx2) - np.max(flx2))
                  amp2lim = amp2range*array([-0.5,0.25]) + (flx2).mean()
	      
	       else:
	          print "Error: need to predict 2nd order"
	  	  amp2lim=None    
            else:
               amp2lim = None
         else:
            amp2lim = None
      
         Z = get_components(xpos,extimg[:,i-15:i+15],array([y1[i],y2[i]]),wheelpos,chatter=chatter,\
	           composite_fit=True,caldefault=True,sigmas=None,amp2lim=amp2lim)   
		
         (params,e_params,flag),input = Z	 
         status = flag[5]  	    
         # here [bg0,bg1,a1,p1,sig1,a2,p2,sig2] = params
         # here [e_bg0,e_bg1,e_a1,e_p1,e_sig1,e_a2,e_p2,e_sig2] = e_params
         if status > 0:
            fx1.append( x[i] )
            fy1.append( params[3] )
            fsig1.append( params[4] )
            e_fx1.append( 15 )
            e_fy1.append( e_params[3] )
            e_fsig1.append( e_params[4] )
            fx2.append( x[i] )
            fy2.append( params[6] )
            fsig2.append( params[7] )
            e_fx2.append( 15 )
            e_fy2.append( e_params[6] )
            e_fsig2.append( e_params[7] )
            bg0.append(params[0])
            bg1.append(params[1])
            e_bg0.append(e_params[0])
            e_bg1.append(e_params[1])
         elif chatter > 1:
            print 'updateFitorder: 1+2nd order updateFitorder failure fit: ' 
	    print 'updateFitorder: INPUT  i: ',i,',   xpos : ',xpos,'   ypos : ',array([y1[i],y2[i]])
	    print 'updateFitorder: params   : ',params
	    print 'updateFitorder: e_params : ',e_params	 

        
   #     positions in first, second and third orders 
   if present3:
     for i in range(q3[0][0]+15,q3[0][-1],30):
   
       if chatter > 4: 
         print " refit first + second + third orders position and sigma"
         print " centre bins ",range(q3[0][0]+15,q3[0][-1],30)
	 
       # only fit high quality 
       q = where(quality[i-15:i+15] == 0)[0] + (i-15) 
      
       if isfinite(y2[i]) & isfinite(y1[i]):
         if ( (abs(y2[i]-y1[i]) < 5) & (abs(y2[i]-y1[i]) >= 1.5) ):
            if predict2nd & (len(SO[0][2]) > 0):
               # find second order prediction for this range, min, max -> amp2lim
	       try:
                 if dis2[0] <= i-15:
                    ilo = dis2.searchsorted(i-15)
                 else: ilo=0
                 if dis2[-1] > i+15: 	 
                    iup = dis2.searchsorted(i+15)+1
                 else: iup = dis2[-1]
                 if iup != ilo: 
		    amp2lim = array([min(SO[0][2][ilo:iup]),max(SO[0][2][ilo:iup])])
		 else:
		    amp2lim = None   
               except:
	         amp2lim = None		 
	    else:
	       print "Error: need to predict 2nd order"  
	       amp2lim = None
         elif ( abs(y2[i]-y1[i]) < 1.5 ): 
            if predict2nd:
               # find second order prediction for this range,but restrict range min, max -> amp2lim
	       try:
                 if dis2[0] <= i-15:
                    ilo = dis2.searchsorted(i-15)
                 else: ilo=0
                 if dis2[-1] > i+15: 	 
                    iup = dis2.searchsorted(i+15)
                 else: iup = dis2[-1]
	         amp2range = abs(min(SO[0][2][ilo:iup])-max(SO[0][2][ilo:iup]))
                 amp2lim = amp2range*array([-0.25,0.25]) + (SO[0][2][ilo:iup]).mean()
	       except:
	          amp2lim = None	 
	    else:
	       print "Error: need to predict 2nd order" 
	       amp2lim = None	      
         else: 
            amp2lim = None
	    
         if isfinite(y3[i]):
            Z = get_components(xpos,extimg[:,i-15:i+15],array([y1[i],y2[i],y3[i]]),wheelpos,chatter=chatter,\
	        composite_fit=True,caldefault=True,sigmas=None,amp2lim=amp2lim)    
	 	
            (params,e_params,flag),input = Z	   	    
            status = flag[5]  	    
            # here [bg0,bg1,a1,p1,sig1,a2,p2,sig2,a3,p3,sig3] = params
            # here [e_bg0,e_bg1,e_a1,e_p1,e_sig1,e_a2,e_p2,e_sig2,e_a3,e_p3,e_sig3] = e_params
            if status > 0:
               fx1.append( x[i] )
               fy1.append( params[3] )
               fsig1.append( params[4] )
               e_fx1.append( 15 )
               e_fy1.append( e_params[3] )
               e_fsig1.append( e_params[4] )
               fx2.append( x[i] )
               fy2.append( params[6] )
               fsig2.append( params[7] )
               e_fx2.append( 15 )
               e_fy2.append( e_params[6] )
               e_fsig2.append( e_params[7] )
               fx3.append( x[i] )
               fy3.append( params[9] )
               fsig3.append( params[10] )
               e_fx3.append( 15 )
               e_fy3.append( e_params[9] )
               e_fsig3.append( e_params[10] )
               bg0.append(params[0])
               bg1.append(params[1])
               e_bg0.append(e_params[0])
               e_bg1.append(e_params[1])
            elif chatter > 1:
               print 'updateFitorder failure fit 1,2,3rd: ' 
	       print 'INPUT  i: ',i,',   xpos : ',xpos,'   ypos : ',array([y1[i],y2[i],y3[i]])
	       print 'params   : ',params
	       print 'e_params : ',e_params	 

   # re-fit the 1,2, 3 order y-offset  and fit background coefficients (remove bad points ???)
 
   if len(fx1) > 0:
      fcoef1 = np.polyfit(array(fx1),array(fy1)-100.,3)
      fsig1coef = np.polyfit(array(fx1),array(fsig1),3)
      fx4 = fx0
      for i in fx1: fx4.append(i)
      fbg0coef = np.polyfit(array(fx4),array(bg0),3)
      fbg1coef = np.polyfit(array(fx4),array(bg1),3)
      y1[q1] = np.polyval(fcoef1,x[q1]) + 100.
   else:
      fsig1coef = sig1coef    
 
   if fit_second & (len(fx2) > 0):
      fcoef2 = np.polyfit(array(fx2),array(fy2)-100.,2)
      fsig2coef = np.polyfit(array(fx2),array(fsig2),2)
      y2[q2] = np.polyval(fcoef2,x[q2]) + 100.
   else:
      fsig2coef = sig2coef    
      
   if fit_third & (len(fx3) > 0):   
      fcoef3 = np.polyfit(array(fx3),array(fy3)-100.,1)
      fsig3coef = np.polyfit(array(fx3),array(fsig3),1)
      y3[q3] = np.polyval(fcoef3,x[q3]) + 100.
   else:
      fsig3coef = sig3coef    
   
   values=(bg0,bg1),(fx0,fx1,fx2,fx3),(fy0,fy1,fy2,fy3),(fsig0,fsig1,fsig2,fsig3)
   errors=(e_bg0,e_bg1),(e_fx0,e_fx1,e_fx2,e_fx3),(e_fy0,e_fy1,e_fy2,e_fy3),(e_fsig0,e_fsig1,e_fsig2,e_fsig3)
   
   y0[q0] = np.polyval(fcoef0,x[q0]) + 100.
   #y1[q1] = np.polyval(fcoef1,x[q1]) + 100.
   #y2[q2] = np.polyval(fcoef2,x[q2]) + 100.
   #y3[q3] = np.polyval(fcoef3,x[q3]) + 100.
   
   fitorder = (present0,present1,oldpres2,oldpres3),(q0,q1,q2,q3), \
      (y0,dlim0L,dlim0U,fsig0coef,sp_zeroth),(y1,dlim1L,dlim1U,fsig1coef,sp_first),\
      (y2,dlim2L,dlim2U,fsig2coef,sp_second),(y3,dlim3L,dlim3U,fsig3coef,sp_third),\
      (x,xstart,xend,sp_all,quality)
  
   if full:   return fitorder, values, errors
   else:      return fitorder

def dAngstrom_dpix_pix (pix,disp,):
   """
   Input pix = distance to anchor in pix units
   Input disp = polynomial for dispersion
   Return Angstroms per pix as a function of x
   """   
   import numpy as np
   
   w1 = np.polyval(disp,pix-0.5) # wavelengths half a pix from centre
   w2 = np.polyval(disp,pix+0.5) 
   return w2-w1   # angstroms per pix

def dAngstrom_dpix_wave (wave, disp, sp_order=1):
   """
   Input wave = wavelengths
   Input disp = polynomial for dispersion
   Return Angstroms per pix as a function of wave
   """         
   import numpy as np
   
   #if sp_order == 1: 
   #   x = np.arange(-370,1250)
   #elif sp_order == 2:
   #   x = np.arange(30,1500)
   #else:
   #   print "error in dAngstrom_dpix_wave: wrong order: ", sp_order
   #   raise      
   #Dinv = polyinverse(disp,x)
   #pix = np.polyval(Dinv, wave)
   pix = pix_from_wave(disp,wave,spectralorder=sp_order)
   return dAngstrom_dpix_pix(pix,disp)
   
def rebin(binin,func,binout, mode='interpolate',N=20): 
   '''  
   Given func(binin) rebin the data to func(binout) 
   
   Either 
     'redistribute' the func values to the new bins (conserve the integral)
   or 
     'interpolate'  the func to the the new bins
   
   
   '''  
   try:
      from convolve import boxcar
   except:
      from stsci.convolve import boxcar
         
   if mode == 'interpolate':
      f = boxcar(func,(N,)) 
      return interpol(binout,binin,f)
      
   elif mode == 'redistribute':
      # see xspec prep routine for method
      print 'TBD'

   else:
      print 'rebin: wrong mode'
      raise    

def spectrumpixshift(w1,spec1, w2,spec2, wmin=None, wmax=None, spectrum=False, 
    delwav=False, chatter=0):
   '''Accurately determine relative wavelength/pixel shift between 2 spectra.
   
   Parameters
   ----------
   w1,spec1, w2,spec2 : array-like
      wavelength, spectrum pairs
      
   kwargs : dict
   
    - **wmin,wmax**: float
   
     limits to region to use 
     
    - **spectrum** : bool
   
     resample 2nd spectra and return second spectrum shifted
     
    - **delwav** : bool
   
    - **chatter** : int

     verbosity
     
   Returns
   -------
   k : int
     shift in pixels. option spectrum `False`, for option delwav `False`
      
   delwav : float
     shift in angstroms. For option spectrum `False`, option delwav `True`
     
   k, (w1,s2) : int, tuple
      pixel shift,  
      tuple of wave, flux for second spectrum shifted and resampled on wavelength first spectrum
      for option spectrum `True`
      
   Notes
   ----- 
   k ~ 1/6 pixel
   [option: resample 2nd spectra ]
   '''
   from scipy.signal import correlate
   import numpy as np
   from scipy import interpolate  
    
   # valid fluxes
   q1 = np.isfinite(spec1)
   w1 = w1[q1].flatten()
   spec1 = spec1[q1].flatten()
   q2 = np.isfinite(spec2)
   w2 = w2[q2].flatten()
   spec2 = spec2[q2].flatten()
   if chatter > 2: print " * len before min, max - ",len(w1),len(spec1),len(w2),len(spec2)
   # interpolating functions
   tck1 = interpolate.splrep(w1, spec1, )
   tck2 = interpolate.splrep(w2, spec2, )
   # limits
   if wmin == None: 
      wmin = np.max([w1[0],w2[0]])
      if chatter > 0: print "spectrumpixshift: wmin = ",wmin
   if wmax == None: 
      wmax = np.min([w1[-1],w2[-1]])
      if chatter > 0: print "spectrumpixshift: wmax = ",wmax
   q1 = (w1 > wmin) & (w1 < wmax)
   #print "q1:-->   ",np.where(q1)
   # put both spectra on the same footing
   w1 = np.arange(int(w1[q1][0]+0.5),int(w1[q1][-1]+0.5),0.5)
   if len(w1) < 1:
      print "ERROR in spectrumpixshift; set to 0"
      print "q1 =  ",q1
      k = 0
      if spectrum: 
         return k, (w2,s2)
      else: return k	 
   s1 = interpolate.splev(w1,tck1,)
   s2 = interpolate.splev(w1,tck2,)
   n = len(s1)
   # find peak in correlation
   k = np.argmax(correlate(s1,s2))+1
   k = n - k
   # shift spectrum s1 by k to match s2
   dw = 0
   try:
     if k > 0:
        dw = (w1[k:]-w1[:-k]).mean()
     elif k < 0:
        dw = (w1[0:k] - w1[-k:]).mean()	
   except: pass  
   if chatter > 2: 
      print "spectrumpixshift: k, dw : ",k,dw
   if spectrum:   # return second spectrum shifted
      if k < 0: 
         w1 = w1[0:n+k]
	 s2 = s2[-k:n]
      if k > 0:
         w1 = w1[k:n]
	 s2 = s2[0:n-k]	 
      return k, (w1,s2)
   elif delwav:
      return dw   
   else:   
      return k 

def sum_Extimage( pha_file_list, sum_file_name='extracted_image_sum.fit', mode='create', 
    ankerlist=None, plotimage=True,correlate=True, correlate_wavewindow=[None,None] ,
    figno=20, shiftlist=[] ,clobber=False, chatter=1 ):
   ''' This routine will create/update/read a summed extracted image.
   
   Parameters
   ----------
   pha_file_list : list
     list of PHA filenames written by calls of `getSpec`
     
   kwargs : dict
   
    - **sum_file_name** : str
    
      file name for sum
       
    - **mode** : str, {'create','read'}
    
      when 'create' make the sum file; when 'read' read the sum file 
      
    - **ankerlist** : list, optional
    
      list of anchor positions
       
    - **plotimage** : bool, optional
    
      make a plot of the image 
    
    - **correlate** : bool, optional
    
      try to determine shifts by correlating the image
    
    - **correlate_wavewindow** : list
      
      when correlate `True` then use only the part of the spectrum within [wavemin, wavemax]
    
    - **figno** : int, optional 
    
      figure number to use 
    
    - **shiftlist** : list, optional
    
      list of shifts to apply 
    
    - **clobber** : bool
    
      write over existing file
    
    - **chatter** : int
    
      verbosity
   
   
   Returns
   -------
   
   When `option=read` the following are returned:
   
   - sumimg : 2D array
     summed image
   - expmap : 2D array
     exposure map for each pixel in summed image
   - exposure : float
     exposure time (maximum)
   - wheelpos : int
     grism wheel position
   - C_1, C_2 : list
     dispersion coefficients
   - dist12 : float
     distance in pixels between the first and second order anchors
   - anker : list
     anchor position in summed image
   - coefficients : tuple
     (coef0,coef1,coef2,coef3,sig0coef,sig1coef,sig2coef,sig3coef)
     curvature and sigma coefficients for the summed image 
   - hdr : fits header
   
   
   Notes
   -----
   
   The anchor point, by default, will be at point [100,500]
   
   mode = 'create' <make new sum file>, 'read' <read sum file>
   
   The anchor position in the pha_file will need to be passed via ankerlist or 
   be given as keyword ANKXIMG, ANKYIMG in the header of the PHA file (it is).
   
   when correlate_wavewindow = [none,none] nothing is done
        = [2300,4000] wavelength range where to do cross correlation on flux to 
	generate corrections to ankx
   
   shiftlist = [None, 0, -2, None ] can be used to force the shifts (in pix) 
      of the given number in the list of spectra (here assumed to be four. 
      List length must equal pha_file_list length. 
   
   Example:
   
   phafiles = ['sw00032150003ugu_1_pha.fits','sw00032150003ugu_2_pha.fits',
   'sw00032150003ugu_3_pha.fits',   'sw00032150003ugu_4_pha.fits',
   'sw00032150003ugu_5_pha.fits',   'sw00032150003ugu_6_pha.fits',
   'sw00032150003ugu_7_pha.fits',   'sw00032150003ugu_8_pha.fits',
   'sw00032150003ugu_9_pha.fits',   'sw00032150003ugu_10_pha.fits',
   'sw00032150003ugu_11_pha.fits', 'sw00032150003ugu_12_pha.fits',
   'sw00032150003ugu_13_pha.fits']
   
   uvotgetspec.sumimage( phafiles, mode='create',chatter=1,clobber=True)
   
   Paul Kuin 2011 (MSSL/UCL)
   '''
   import pyfits
   import numpy as np
   import uvotmisc
   import pylab as plt
   
   if plotimage & (mode == 'create'):
      fig1 = plt.figure(figno)
      plt.clf()
      fig2 = plt.figure(figno+1)
      plt.clf()
   
   m = -1
   img = np.zeros([200,2000],dtype=float)
   img2 = np.zeros([200,2000],dtype=float)
   expmap = np.zeros([200,2000],dtype=float)
   # quamap = np.zeros([200,2000],dtype=float)  # need quality map to extracted image in the pha file
   tot_exposure = 0.
   tstart = 999999999.
   tstop = 0.
   headers = list()
   legend= []
   ysh = [0]
   yshift = 0.
   if mode == 'create':         
      for m in range(len(pha_file_list)):
         pha_file = pha_file_list[m]
         d = pyfits.getdata(pha_file,2)
	 #print m," - ",pha_file
	 if m == 0:
	    w1 = d['lambda']
	    f1 = d['flux']
	    w1 = w1[np.isfinite(f1)]
	    f1 = f1[np.isfinite(f1)]
	    norm = f1[(np.abs(w1-w1.mean()) < 0.35 * w1.mean())].mean()
	    f1 /= norm
	    #print " len w1, f1 = (",len(w1),',',len(f1),')' 
	 else:
            w2 = d['lambda']
	    f2 = d['flux']
	    w2 = w2[np.isfinite(f2)]
	    f2 = f2[np.isfinite(f2)]/norm
	    #print " len w+, f+ = (",len(w2),',',len(f2),')' 
            ysh.append( spectrumpixshift(w1,f1, w2,f2, wmin=correlate_wavewindow[0], wmax=correlate_wavewindow[1], ) )
      # adjust ysh to the mean 
      if len(shiftlist) == len(pha_file_list): 
         for ys in range(len(shiftlist)): 
	     if shiftlist[ys] != None: 
	        ysh[ys] = shiftlist[ys]
		print "updated shift for "+pha_file_list[ys]+" to ",ysh[ys]
      print "shifts are now (in A):",ysh		
      ysh -= np.mean(ysh)
      # convert ysh (per 0.5 angstrom) to pixels 
      ysh = np.array( ysh/6+0.5 , dtype=int )	    
      print "plan to apply pixel shifts to images of magnitude = ",ysh
      if not correlate: 
         ysh = 0 * ysh
	 print "reset shifts ",ysh
      for m in range(len(pha_file_list)):
         pha_file = pha_file_list[m]
         f = pyfits.open(pha_file)
	 headers.append( f[1].header )
         if chatter > 0 : 
            print 'reading '+pha_file+'   in mode='+mode
            f.info()
         try:
            ankx = f[3].header['ANKXIMG'] + ysh[m]
            anky = f[3].header['ANKYIMG']
         except:
            ankx,anky = ankerlist[m]
            pass
	 ankx = int(ankx+0.5)
	 anky = int(anky+0.5)   
         expo = f[1].header['exposure']
   
         if chatter > 0: 
            print 'ankx, anky = [',ankx,', ',anky,' ]'
	    print 'exposure   = ',expo
	    print 'ankx was shifted by ',ysh[m],' pix'

         if anky <= 100:
            y0 = 100-anky     
            y1 = 200
            y2 = 0
            y3 = 100+anky
         else:
            y0 = 0
            y1 = 300-anky
            y2 = anky-100
	    y3 = 200
	 	
         x0 = 0
         x2 = ankx-500
         if ankx <= 500: 
            x0 = 500-ankx
            x2 = 0
         y23,x3 = f[3].data.shape
         x1 = x3 - x2
         if x1 > 2000: 
            x1=2000
	    x3=x2+2000
         if chatter > 2: 	 
            print img[y0:y1,x0:x1].shape
            print f[3].data[y2:y3,x2:x3].shape
            print y0,y1,y2,y3 
            print x0,x1,x2,x3
      	 
	 #  add to sum
	 tot_exposure += expo
         img[y0:y1,x0:x1] += f[3].data[y2:y3,x2:x3] 
         expmap[y0:y1,x0:x1] += expo 
         img2[y0:y1,x0:x1] = f[3].data[y2:y3,x2:x3] 
	 #quamap[y0:y1,x0:x1] += f[4].data[y2:y3,x2:x3] 
	 
	 if m == 0:   # calculate a sensible value for the shift of the spectra
	    xlam = f[2].data['lambda']
	    qys = abs(xlam - xlam.mean()) < 0.2*xlam.mean() 
	    yshift = f[2].data['flux'][qys].mean()
	 plt.figure(figno)   
	 p1 = plt.plot(f[2].data['lambda'],(m-1)*yshift+f[2].data['flux'],)
	 legend.append(pha_file)
	 plt.legend(legend)
	 plt.title("images offset in flux by %10.3e"%(yshift))
	 plt.xlabel('uncorrected wavelength ($\AA$)')
	 plt.ylabel('flux + shift (erg cm-2 s-1 A-1')
	 plt.figure(figno+1)
	 plt.plot( img2[80:120,:].sum(0) )
	 plt.grid()
	 plt.legend(legend)
	 plt.title('adding image: pixels summed y[80:120] to check alignment')
	 f.close()
	
#     create file with sum extracted image
	 
      hdr = headers[0]      	
      fsum = pyfits.PrimaryHDU(data=img,header=hdr)
      hdulist = pyfits.HDUList(fsum)
      hdulist[0].header.update('EXPOSURE',tot_exposure,comment='total exposure time')
      hdulist[0].header.update('EXTNAME','SPECTRUMSUM')
      hdulist[0].header.update('EXPID','989979969')
      
      for head in headers:
         hist = head.get_history()
	 filetag = head['filetag']
	 hdulist[0].header.add_history(" copy header[1] of filetag "+filetag)
	 tstart = min([head['tstart'],tstart])
	 tstop  = max([head['tstop'],tstop])
         for h in hist:
            hdulist[0].header.add_history(h)
      for pha_file in pha_file_list:	    
         hdulist[0].header.add_history('added file'+pha_file)
      hdulist[0].header.update('TSTART',tstart)
      hdulist[0].header.update('TSTOP',tstop)
      exthdu = pyfits.ImageHDU(expmap) # add extension for the expmap 
      hdulist.append(exthdu)
      hdulist[1].header.update('EXTNAME','EXPOSUREMAP')
      # quahdu = pyfits.ImageHDU( quahdu )
      # hdulist.append(quahdu)
      #hdulist[2].header.update('EXTNAME','QUALITYMAP')
      hdulist.writeto(sum_file_name,clobber=clobber)
      hdulist.close()
      print "total exposure of images = ",tot_exposure
	 	 
   elif mode == 'read':    #  read the summed, extracted image and header
         hdulist  = pyfits.open(sum_file_name)
	 hdr = hdulist[0].header
         exposure = hdr['exposure']
         wheelpos = hdulist[0].header['wheelpos']
	 sumimg   = hdulist[0].data
         hist     = hdulist[0].header.get_history()
	 if len(hdulist) > 1:
            expmap   = hdulist[1].data
	 else: 
	    expmap = None   
	 C_1 = list([])
	 C_2 = list([])
	 coef0 = list()
	 coef1 = list()
	 coef2 = list()
	 coef3 = list()
	 sig0coef = list()
	 sig1coef = list()
	 sig2coef = list()
	 sig3coef = list()
	 dist12 = None
	 C_1.append(uvotmisc.get_keyword_from_history(hist,'DISP1_0'))
	 C_1.append(uvotmisc.get_keyword_from_history(hist,'DISP1_1'))
	 C_1.append(uvotmisc.get_keyword_from_history(hist,'DISP1_2'))
	 C_1.append(uvotmisc.get_keyword_from_history(hist,'DISP1_3'))
	 C_1.append(uvotmisc.get_keyword_from_history(hist,'DISP1_4'))
	 C_1 = np.array(C_1,dtype=float)
	 C_2.append(uvotmisc.get_keyword_from_history(hist,'DISP2_0'))
	 C_2.append(uvotmisc.get_keyword_from_history(hist,'DISP2_1'))
	 C_2.append(uvotmisc.get_keyword_from_history(hist,'DISP2_2'))
	 C_2 = np.array(C_2,dtype=float)
	 dist12 = float(uvotmisc.get_keyword_from_history(hist,'DIST12'))
	 anchor1 = uvotmisc.get_keyword_from_history(hist,'anchor1')
	 anker = np.array([ float(anchor1.split(',')[0].split('(')[1]), float(anchor1.split(',')[1].split(')')[0]) ] )
	 coef0.append(uvotmisc.get_keyword_from_history(hist,'COEF0_0'))
	 coef0.append(uvotmisc.get_keyword_from_history(hist,'COEF0_1'))
	 coef1.append(uvotmisc.get_keyword_from_history(hist,'COEF1_0'))
	 coef1.append(uvotmisc.get_keyword_from_history(hist,'COEF1_1'))
	 coef1.append(uvotmisc.get_keyword_from_history(hist,'COEF1_2'))
	 coef1.append(uvotmisc.get_keyword_from_history(hist,'COEF1_3'))
	 coef2.append(uvotmisc.get_keyword_from_history(hist,'COEF2_0'))
	 coef2.append(uvotmisc.get_keyword_from_history(hist,'COEF2_1'))
	 coef2.append(uvotmisc.get_keyword_from_history(hist,'COEF2_2'))
	 coef3.append(uvotmisc.get_keyword_from_history(hist,'COEF3_0'))
	 coef3.append(uvotmisc.get_keyword_from_history(hist,'COEF3_1'))
	 coef0 = np.array(coef0,dtype=float)
	 coef1 = np.array(coef1,dtype=float)
	 coef2 = np.array(coef2,dtype=float)
	 coef3 = np.array(coef3,dtype=float)
	 sig0coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF0_0'))
	 sig0coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF0_1'))
	 sig0coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF0_2'))
	 sig1coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF1_0'))
	 sig1coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF1_1'))
	 sig1coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF1_2'))
	 sig1coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF1_3'))
	 sig2coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF2_0'))
	 sig2coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF2_1'))
	 sig2coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF2_2'))
	 sig3coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF3_0'))
	 sig3coef.append(uvotmisc.get_keyword_from_history(hist,'SIGCOEF3_1'))
	 sig0coef = np.array(sig0coef,dtype=float)
	 sig1coef = np.array(sig1coef,dtype=float)
	 sig2coef = np.array(sig2coef,dtype=float)
	 sig3coef = np.array(sig3coef,dtype=float)
	 if chatter > 0:
	    print 'first order dispersion = ',C_1
	    print 'second order dispersion= ',C_2
	    print '1-2 order distance     = ',dist12
	 return sumimg, expmap, exposure, wheelpos, C_1, C_2, dist12, anker, (coef0,
	        coef1,coef2,coef3,sig0coef,sig1coef,sig2coef,sig3coef), hdr   

def sum_PHAspectra(phafiles, wave_shifts=[], exclude_wave=[], ignore_flags=True, 
      interactive=True, outfile=None, figno=[14], ylim=[],chatter=1, clobber=True):
   '''Read a list of phafiles. Sum the spectra after applying optional wave_shifts. 
   
   Parameters
   ----------
   phafiles : list
      list of filenames
   wave_shifts : list
      list of shifts to add to the wavelength scale; same length as phafiles
   exclude_wave : list
      list of lists of exclude regions; same length as pha files; one list per file
   ignore_flags : bool
      do not automatically convert flagged sections of spectrum to exclude_wave regions 
   interactive : bool
      if False, the program will only use the given wave_shifts, and exclude_regions
   outfile : str
      name for output file. If "None" then an array of data for debug is returned
   ylim : list
      force limits of Y-axis figure      
   figno : int, or list
      numbers for figures or (if only one) the start number of figures     
   
   Returns
   -------
   debug information when `outfile=None`.
   
   Notes
   -----
   Two figures are shown, one with flux for all spectra after shifts, one with 
   broad sum of counts in a region which includes the spectrum, unscaled, not even
   by exposure. 
   
   '''
   import pyfits
   import numpy as np
   from scipy import interpolate
   import pylab as plt
   import copy
   
   # first create the wave_shifts and exclude_wave lists; then call routine again to 
   # create output file (or if None, return result)
   
   nfiles = len(phafiles)
   # assume phafiles are all valid paths
   if chatter > 2:
      print " INPUT ============================================================================="
      print "sum_PHAspectra(phafiles, wave_shifts= , exclude_wave= , ignore_flags=%s,\n" %(ignore_flags)
      print "interactive=%s, outfile=%s, \nfigno=%s, chatter=%i, clobber=%s)\n" % (interactive,outfile,figno,chatter,clobber)
      print " where "
      print "phafiles=",phafiles
      print "wave_shifts=",wave_shifts
      print "exclude_wave=",exclude_wave
      print "===================================================================================="
   exclude_wave_copy = copy.deepcopy(exclude_wave)  

   if (interactive == False) & (len(wave_shifts) == nfiles) & (len(exclude_wave) == nfiles):
      if chatter > 1 : print "merging spectra "
      # create the summed spectrum
      result = None
      # find wavelength range
      wmin = 7000; wmax = 1500
      f = []    #  list of open fits file handles
      for fx in phafiles:
         f.append( pyfits.open(fx) )
      for fx in f:	 
	 q = np.isfinite(fx[2].data['flux'])
	 w1 = np.min(fx[2].data['lambda'][q])
	 w2 = np.max(fx[2].data['lambda'][q])
	 wmin = np.min([wmin, w1] ) 
	 wmax = np.max([wmax, w2] )
      if chatter > 1: 
	    print 'wav min ',wmin
	    print 'wav max ',wmax
	 
      # create arrays - output arrays
      wave = np.arange(int(wmin+0.5), int(wmax-0.5),1)  # wavelength in 1A steps
      nw = len(wave)                     # number of wavelength points
      flux = np.zeros(nw,dtype=float)	 # flux
      error = np.zeros(nw,dtype=float)   # mean RMS errors in quadrature
      nsummed = np.zeros(nw,dtype=int)   # number of spectra summed for the given point - if only one, 
                                         # add the typical RMS variance found for points with multiple spectra
      # local arrays      					 
      err_in  = np.zeros(nw,dtype=float)   # error in flux
      err_rms = np.zeros(nw,dtype=float)   # RMS error from variance
      mf = np.zeros(nw,dtype=float)        # mean flux
      wf = np.zeros(nw,dtype=float)        # weighted flux
      var = np.zeros(nw,dtype=float)         # variance 
      err = np.zeros(nw,dtype=float)       # RMS error
      wgt = np.zeros(nw,dtype=float)       # weight
      wvar= np.zeros(nw,dtype=float)       # weighted variance
      one = np.ones(nw,dtype=int)          # unit
      D = []
      for i in range(nfiles):
         if chatter > 1: 
	    print 'processing file number ',i,'  from ',fx[1].header['date-obs']
         fx = f[i]
	 excl = exclude_wave[i]
         W = fx[2].data['lambda']+wave_shifts[i]
	 F = fx[2].data['flux']   
	 E = fx[2].data['fluxerr']
	 p = np.isfinite(F) & (W > 1600.)
	 fF = interpolate.interp1d( W[p], F[p], )
	 fE = interpolate.interp1d( W[p], E[p]+0.01*F[p], ) 
	 
         M = np.ones(len(wave),dtype=bool)     # mask
	 M[wave < W[p][0]] = False
	 M[wave > W[p][-1]] = False
	 while len(excl) > 0:
	    try:
	       w1,w2 = excl.pop()
	       if chatter > 1: print 'excluding from file ',i,"   ",w1," - ",w2
	       M[ (wave >= w1) & (wave <= w2) ] = False
	    except: pass 
	 
	 flux[M]    = fF(wave[M])
	 error[M]   = fE(wave[M])
	 nsummed[M] += one[M] 
	 mf[M]      += flux[M]                 # => mean flux 
	 wf[M]      += flux[M]/error[M]**2     # sum weight * flux
	 wvar[M]    += flux[M]**2/error[M]**2  # sum weight * flux**2
	 var[M]     += flux[M]**2    	       # first part 	
	 err[M]     += error[M]**2
	 wgt[M]     += 1.0/error[M]**2    # sum weights
         D.append(((W,F,E,p,fF,fE),(M,wave,flux,error,nsummed),(mf,wf,wvar),(var,err,wgt)))

      exclude_wave = copy.deepcopy(exclude_wave_copy)
      mf = mf/nsummed              # mean flux
      var = np.abs(var/nsummed - mf**2)    # variance in flux (deviations from mean of measurements)
      err = err/nsummed            # mean variance from errors in measurements 	
      wf = wf/wgt                  # mean weighted flux
      wvar = np.abs(wvar/wgt - wf**2)      # variance weighted from measurement errors		
      # perform a 3-point smoothing? (since PSF spans several pixels)
      # TBD
      # variance smoothing depending on number of spectra summed?
      svar = np.sqrt(var)
      serr = np.sqrt(err)
      result = wave, wf, wvar, mf, svar, serr, nsummed, wave_shifts, exclude_wave 

      # debug : 	 
      D.append( ((W,F,E,p,fF,fE),(M,wave,flux,error,nsummed),(mf,wf,wvar),(var,err,wgt)) )
      	 	 
      for fx in f:		# cleanup
         fx.close()
 
      if outfile == None:
         return D 
      else: 
         if chatter > 1: print "writing output to file: ",outfile
         #if not clobber:
	    # TBD test presence outfile first
	    
         fout = open(outfile,'w')
	 fout.write("#merged fluxes from the following files\n")
	 for i in range(nfiles): 	      
	    fout.write("#%2i,  %s, wave-shift:%5.1f, exclude_wave=%s\n" % (i,phafiles[i],wave_shifts[i],exclude_wave[i]))
	 fout.write("#columns: wave(A),weighted flux(erg cm-2 s-1 A-1), variance weighted flux, \n"\
	    +"#          flux(erg cm-2 s-1 A-1), flux error (deviations from mean),  \n"\
	    +"#          flux error (mean noise), number of data summed\n")
	 for i in range(nw):
	    if np.isfinite(wf[i]): 
               fout.write( ("%8.2f  %12.5e  %12.5e  %12.5e  %12.5e  %12.5e  %4i\n") % \
	               (wave[i],wf[i],wvar[i],mf[i],svar[i],serr[i],nsummed[i]))
         fout.close()		       
	 
   else:
      if len(wave_shifts)  != nfiles: wave_shifts = []
      if len(exclude_wave) != nfiles: exclude_wave = []
      if not interactive:
         if chatter > 1: print "Determine valid ranges for each spectrum; determine shifts"
	 exwave = []
         for i in range(nfiles):
	    if len(wave_shifts)  != nfiles: wave_shifts.append(0)
	    excl = []
	    if len(exclude_wave) == nfiles: excl = exclude_wave[i]
	    if not ingnore_flags:
      	       f = pyfits.open(phafiles[i])
	       W  = f[2].data['lambda']
	       FL = f[2].data['quality']
	       f.close()
	       ex = []
	       if FL[0] != 0: ex=[0]
	       for i in range(1,len(W)):
	          same = ((W[i] == 0) & (W[i-1] == 0)) | ( (W[i] != 0) & (W[i-1] !=0) )
		  good = (FL[i] == 0)
		  if not same:
		     if good: ex.append[i]
		     else: ex = [i]
	          if len(ex) == 2: 
		     excl.append(ex)
		     ex = []
		  if (i == (len(W)-1)) & (len(ex) == 1): 
		     ex.append(len(W))
		     excl.append(ex) 
            exwave.append(excl) 		       			
	 exclude_wave = exwave
	    
	 if not ingnore_flag: sum_PHAspectra(phafiles, wave_shifts=wave_shifts, \
	    exclude_wave=exclude_wave, ignore_flags=True, interactive=False, \
	    outfile=outfile, figno=figno, chatter=chatter, clobber=clobber)
		 	
      else:    # interactively adjust wavelength shifts and clipping ranges
         # first flag the bad ranges for each spectrum
         if chatter > 1: print "Determine valid ranges for each spectrum; determine shifts"
         for i in range(nfiles):
	    if chatter > 1: 
	       print "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
	       print " valid ranges for file number %i - file name = %s\n" % (i,phafiles[i])
	       		 
      	    f = pyfits.open(phafiles[i])
	    W = f[2].data['lambda']
	    F = f[2].data['flux']
	    E = f[2].data['fluxerr']
	    FL = f[2].data['quality']
	    try:
  	       COI = f[2].data['sp1_coif']
	       do_COI = True
	    except: 
	       COI = np.ones(len(W)) 
	       do_COI = False  
	    q = np.isfinite(F)

	    if figno != None: plt.figure(figno[0])
	    plt.clf()
	    OK = True
	    if len(exclude_wave) == nfiles:
	       print "wavelength exclusions for this file are: ",exclude_wave[i]
     	       ans = raw_input(" change this ? (y/N) : ")
	       if ans.upper()[0] == 'Y' :  OK = True
	       else: OK = False
            if chatter > 1: print "update exclude wave OK = ",OK	       
	    nix1 = 0
	    while OK:     # update the wavelength exclusions
	       try:
	          nix1 += 1
		  OK = nix1 < 10
	          excl = []
		  #   consider adding an image panel (resample image on wavelength scale)
		  #
		  plt.clf()
	          plt.subplot(2,1,1)
	          plt.fill_between(W[q],F[q]-E[q],F[q]+E[q],color='y',alpha=0.4, )
	          plt.plot(W[q],F[q],label='current spectrum + error' ) 
	          plt.title(phafiles[i]+' FLAGGING BAD PARTS ')
		  plt.legend(loc=0)
		  if len(ylim) == 2: plt.ylim=ylim
		  plt.xlabel('wavelength in $\AA$')
	          plt.subplot(2,1,2)
	          plt.plot(W[q],FL[q],ls='steps',label='QUALITY FLAG')
	          if do_COI: plt.plot(W[q],COI[q],ls='steps',label='COI-FACTOR')
		  plt.legend(loc=0)
		  plt.xlabel('wavelength in $\AA$')
	       	  
		  EXCL = True
		  nix0 = 0
		  while EXCL:
		        nix0 +=1 
			if nix0 > 15: break
		        print "exclusion wavelengths are : ",excl
		        ans = raw_input('Exclude a wavelength region ?')
		        EXCL = not (ans.upper()[0] == 'N')
			if ans.upper()[0] == 'N': break		     
		        ans = input('Give the exclusion wavelength range as two numbers separated by a comma: ')
		        excl.append(list(ans))
		  exclude_wave.append( excl )
		  OK = False
	       except:
	          print "problem encountered with the selection of exclusion regions"
	          print "try again"
	         	  
         # get wavelength shifts for each spectrum
	    # if already passed as argument:  ?
	 
	 for i in range(nfiles):
	    print " number  filename "
	    print " %2i --- %s\n" % (i,phafiles[i])
	 try:   
	    fselect = input(" give the number of the file to use as reference, or 0 : ")	  
	    ref = pyfits.open(phafiles[fselect])   
         except: 
	    fselect = 0
	    ref = pyfits.open(phafiles[0])
	 refW = ref[2].data['lambda']
	 refF = ref[2].data['flux']
	 refE = ref[2].data['fluxerr']
	 refexcl = exclude_wave[fselect]   
	 #q = np.ones(len(refW),dtype=bool)
	 q = np.isfinite(refF) & (refW > 1600.)
	 for ex in refexcl:
            q[ (refW > ex[0]) & (refW < ex[1]) ] = False

	 if figno != None: 
	    if len(figno) > 1: plt.figure(figno[1]) 
	 for i in range(nfiles):
	    if i == fselect:
	       wave_shifts.append( 0 )
	    else:
	       f = pyfits.open(phafiles[i])
	       W = f[2].data['lambda']
	       F = f[2].data['flux']
	       E = f[2].data['fluxerr']
	       excl = exclude_wave[i]
	       #p = np.ones(len(W),dtype=bool)
	       p = np.isfinite(F) & (W > 1600.)
	       for ex in excl:
	          p[ (W > ex[0]) & (W < ex[1]) ] = False

	       OK = True
	       sh = 0
	       while OK: 
		  plt.clf()
	          plt.plot(refW[q],refF[q],'k',lw=1.5,ls='steps',label='wavelength reference') 	  
	          plt.fill_between(refW[q],(refF-refE)[q],(refF+refE)[q],color='k',alpha=0.2) 
		  
	          plt.plot(W[p]+sh,F[p],'b',ls='steps',label='spectrum to shift') 	  
	          plt.fill_between(W[p]+sh,(F-E)[p],(F+E)[p],color='b',alpha=0.2)
	          
		  plt.plot(W[p],F[p],'r--',alpha=0.6,lw=1.5,label='original unshifted spectrum') 	  		  
		  
		  plt.title('file %i applied shift of %e' % (i,sh))
		  plt.xlabel('wavelength $\AA$')
		  if len(ylim) == 2: plt.ylim=ylim
		  plt.legend(loc=0)
		  try:
  		     sh1 = input("give number of Angstrom shift to apply (e.g., 2.5, 0=done) : ")  
                     if np.abs(sh1) < 1e-3:
		        wave_shifts.append(sh)
			OK = False
	          except: 
		     print "input problem. No shift applied"
		     sh1 = 0
		  
		  if not OK: print 'should have gone to next file'      
	          sh += sh1
		  if chatter > 1: print "total shift = ",sh," A" 
		  #plt.clf()
	          #plt.plot(refW[q],refF[q],'k',ls='steps',label='wavelength reference') 	  
	          #plt.fill_between(refW[q],(refF-refE)[q],(refF+refE)[q],color='k',alpha=0.2) 
	          #plt.plot(W[p],F[p],'m',alpha=0.5,ls='steps',label='original unshifted spectrum') 	  		  
	          #plt.plot(W[p]+sh,F[p],'b',ls='steps',label='spectrum to shift') 	  
	          #plt.fill_between(W[p]+sh,(F-E)[p],(F+E)[p],color='b',alpha=0.2)
		  #plt.title('file %i applied shift of %e' % (i,sh))
		  #plt.legend(loc=0)
		  #plt.xlabel('wavelength $\AA$')
	 if chatter > 1: 
	    print "selected shifts = ",wave_shifts
	    print "selected exclude wavelengths = ",exclude_wave     
	 #
	 #  TBD use mean of shifts instead of reference spectrum ?
	 #       
	 C = sum_PHAspectra(phafiles, wave_shifts=wave_shifts, exclude_wave=exclude_wave, ignore_flags=True, 
              interactive=False, outfile=outfile, figno=None, chatter=chatter, clobber=True)   
	 return C       
  
def coi_func2(pixno,wave,countrate,bkgrate,sig1coef=[3.2],option=2,
   fudgespec=1.0,coi_length=26,frametime=0.0110302, background=False,
   sigma1_limits=[2.6,4.0], trackwidth = 1.0, ccc = [0.,-0.,0.40],
   ccb = [0.,-0.67,1.0], debug=False,chatter=1):
   return coi_func(pixno,wave,countrate,bkgrate,sig1coef=[4.5],option=2,
   fudgespec=1.0,coi_length=26,frametime=0.0110302, background=False,
   sigma1_limits=[3.0,7.5], trackwidth = 1.0, ccc = [0.,-0.,0.40],
   ccb = [0.,-0.67,1.0], debug=False,chatter=1)
   
def coi_func(pixno,wave,countrate,bkgrate,sig1coef=[3.2],option=2,
   fudgespec=1.0,coi_length=26,frametime=0.0110302, background=False,
   sigma1_limits=[2.6,4.0], trackwidth = 2.5, ccc = [-1.5,+1.5,-1.5,+1.5,-1.5,+1.5,+0.995],
   ccb = [+0.72,-0.72,0.995], ca=[0,0,3.2],cb=[0,0,3.2],debug=False,chatter=1):
   #ccb = [+2.68,-2.68,-3.3,+3.3,0.995], debug=False,chatter=1): - proper background 
   '''Compute the coincidence loss correction factor to the (net) count rate 
   as a function of wavelength  EXPERIMENTAL
   
   Parameters
   ----------
   pixno : array-like
      pixel number with origen at anchor
   wave : array-like
      wavelength in A
   countrate : array-like
      input count net rate must be aperture corrected
   bkgrate : array-like
      background rate for trackwidth
   kwargs : dict
   
      - **sig1coef** : list
      
        polynomial coefficients
	
      - **frametime** : float
      
        CCD frame time in seconds
	
      - **trackwidth** : float
      
        width of the extraction in standard deviations of the profile matched across the spectrum
	
      - **option** : int 
      
        . option = 1 : classic coi-loss, but spectrum is box like 10x32 pix across spectrum
	
        . option = 2 : bkg classic coi-loss, total (spectrum*poly+bkg*poly) with 
                     polynomial corrections for extended coi-loss. 
		     classical limit for ccc= [0,0,1] ; ccb[0,0,1] 
		     
      - **background** : bool
      
        if the background is `True` an interpolated function for the coi 
	correction factor in the background count rate is returned
        
	if the background is `False` an interpolated function for the 
	coi correction factor in the net target count rate is returned
      		       
      
   
   Returns
   -------
       coi_func : scipy.interpolate.interpolate.interp1d
          if **background** is `True` an interpolated function for the coi correction 
          factor in the background count rate while if **background** is `False` an 
          interpolated function for the coi correction factor in the net target 
          count rate is returned 
   
   Notes
   -----   
   defaults to the background coincidence loss equivalent to an area of 
   315 sub-pixels (about pi*5"^2 on the detector) 
   
   Also see the discussion of coincidence loss in Breeveld et al. (2010).
   Her correction for high background + high source rate was used as inspiration.
   
   - 2012-03-21 NPMK initial version
   - 2012-07-04 NPMK added into option 1 the white-correction for high 
     background (photometry) from Alice Breeveld (2010) 
   - 2012-07-24 NPMK modified source area to be same as background area  
   - 2012-07-24 NPMK start modifications extended coi-model 
   - 2012-09-25 NPMK simplify. Add extended coi-loss as polynomial using classic coi as approx. 
                   coefficients TBD. 
   - 2012-10-10 NPMK temporary option 3 to address consistent approach with Breeveld et al. and 
       the coi-work on point sources. Basically, it is not a reduction in the background but 
       a lack of accounting for additional losses in the main peaks (due to surrounding 
       high background levels stealing counts from source). Option 2 has now been optimized 
       to work. Basically, there are multiple practical solutions to the problem, the third 
       option will be more in line with the theoretical model for coincidence loss in the 
       UVOT. 	   
   '''   
   import uvotmisc
   import numpy as np
   try:
     from uvotpy import uvotgetspec as uvotgrism
   except:  
     import uvotgrism
   try:
      from convolve import boxcar
   except:
      from stsci.convolve import boxcar   
   from scipy import interpolate
    
   if not do_coi_correction:   # global - use when old CALDB used for fluxes.
      # set factor to one:
      return interpolate.interp1d(wave,wave/wave,kind='nearest',bounds_error=False,fill_value=1.0 ) 
      
   if type(trackwidth) != float:
      raise TypeError ( "trackwidth is not of type float, trackwidth type: ",type(trackwidth) )   
  
   alpha = (frametime - 0.000171)/frametime
   
   # mask bad and problematic data 
   if background: v = np.isfinite(countrate) &  (bkgrate > 1e-8) 
   else: v = np.isfinite(countrate) & np.isfinite(bkgrate) & (countrate > 1e-8) & (bkgrate > 1e-8) 
   countrate = countrate[v]
   bkgrate   = bkgrate[v]
   pixno     = pixno[v]
   wave      = wave[v]
   
   # reset v
   v = np.ones(len(countrate),dtype=bool)
   
   # correct cpf to 550 subpixels in size, 5 sigma total width (~17.5). (about 6.5" circle on lenticular filter)
   # this initial setting was changed to 315 to match to the Poole method for photometry, but actually, may be 
   # the correct choice after all for the background-background coi-correction (high backgrounds), see Kuin (2013)
   # study on coincidence loss. 
   
   sigma1 = np.polyval(sig1coef, pixno)
   sigma1[ sigma1 > sigma1_limits[1] ] = sigma1_limits[1]
   sigma1[ sigma1 < sigma1_limits[0] ] = sigma1_limits[0]
   
   # scaling the counts per frame 
   #  - get the background counts per pixel by dividing through 2*sigma1*trackwidth
   #  - scale background to number of pixels used in photometry coi-background  correction
   bgareafactor = 315.0/(2 *sigma1*trackwidth)  # strip 'trackwidth' sigma halfwidth determined by input
   factor = 315.0/(2 *sigma1*trackwidth)        # strip 'trackwidth' sigma halfwidth determined by input
   specfactor = 315.0/(2.*sigma1*2.5)           # aperture correction was assumed done on the input rate to be consistent with the 2.5 sigma Eff. Area
   # coi-area spectrum in limit (net = zero) must be background one, so same factor
   # Very high backgrounds deviate (Breeveld et al. 2010, fig 6; ccb=[+2.68,-2.68,-3.3,+3.3,0.995] matches plot)
   
   # one pixel along the spectrum, 2 x sigma x trackwidth across, aperture corrected countrate (not bkgrate)
   # works for the lower count rates: total_cpf = boxcar( (countrate*fudgespec + bkgrate) * frametime  ,(coi_length,))
   if not background: 
      tot_cpf = obs_countsperframe = boxcar((countrate + bkgrate) * frametime, (coi_length,))
      net_cpf = boxcar( countrate * frametime, (coi_length,))
   bkg_cpf = bkg_countsperframe = boxcar( bkgrate * frametime, (coi_length,) )  
   # PROBLEM: boxcar smooth does not work for pixels on the array ends. downturn coi-correction. Need something better.
   
   if chatter > 3: 
	 print "alpha  = ",alpha
	 print "number of data points ",len(countrate),"  printing every 100th"
	 print " i    countrate    obs counts/frame "
	 for ix in range(0,len(countrate),10):
	   if background: print "%4i %12.5f %12.5f " % (ix, bkgrate[ix],bkg_cpf[ix])
	   else: print "%4i %12.5f  %12.5f" % (ix, countrate[ix],obs_countsperframe[ix])
	   
   try:
	 	 
      bkg_cpf_incident = (-1.0/alpha) * np.log(1.0 - bgareafactor*bkg_countsperframe)/(bgareafactor)
      
      if option == 1:   # default 
	 # classic coi formula
         yy = 1.0 - specfactor*obs_countsperframe
	 v[ yy < 1e-6 ] = False
	 yy[ yy < 1e-6 ] = 1e-6    # limit if yy gets very small or negative !!
         obs_cpf_incident = (-1.0/alpha) * np.log(yy)/specfactor
	 
      if option == 2: 	 
	 # new default reverts to classic coi-formula when all coef = 0 except the last one, which must be 1. 
         # extended coi-loss coefficients ccc, ccb 
	 if background: v[bkg_cpf*factor >= 0.9999] = False 
	 else: v[tot_cpf*factor >= 0.9999] = False	 
         ccc = np.asarray(ccc)
         ccb = np.asarray(ccb)
	 # extended coi-loss correction of counts per frame  - add polynomial corrections
         if not background: 
	    total_cpf  = obs_countsperframe = boxcar((countrate * np.polyval(ccc,tot_cpf*specfactor) + \
	                 bkgrate * np.polyval(ccb,bkg_cpf*factor)) * frametime , (coi_length,)) 
         bkg_countsperframe = boxcar( bkgrate * np.polyval(ccb,bkg_cpf*factor) * frametime , (coi_length,)) 	   
         bkg_cpf_incident = (-1.0/alpha) * np.log(1.0 - factor*bkg_countsperframe)/(bgareafactor)
         if not background:
	    yy = 1.0 - factor*total_cpf
	    v[ yy < 1e-4 ] = False
	    yy[ yy < 1e-4 ] = 1e-4    # limit if yy gets very small or negative !!
            obs_cpf_incident = (-1.0/alpha) * np.log(yy)/factor
	 	     	 
      if option == 3: 	 
	 # extension reverts to classic coi-formula  . 
         # extended coi-loss coefficients ccc, ccb acting on variable z = cpf * ( 1 - cpf )
	 # high background coi-loss correction fits FIG 6 in Breeveld et al. 
	 if background: v[bkg_cpf*factor >= 0.9999] = False 
	 else: v[tot_cpf*factor >= 0.9999] = False	 
         # convert to actual cpf:
	 ##CPFnet = net_cpf*specfactor
	 CPFtot = tot_cpf*specfactor
         CPFbkg = bkg_cpf*factor
	 z_tot = CPFtot * (1. - CPFtot)   # binomial type of variable
	 z_bkg = CPFbkg * (1. - CPFbkg)
	 
	 # extended coi-loss CPF correction of counts per frame  - correct with polynomial corrections in z
         if not background: 
	    CPFtot_corr = CPFnet*(1. + np.polyval(ca,z_tot)) + CPFbkg*(1. + np.polyval(cb,z_tot))		          
	 CPFbkg_corr = CPFbkg*(1 + np.polycal(cb,z_bkg))  
         CPFbkg_in   =  (-1.0/alpha) * np.log(1.0 - CPFbkg_corr)
	 bkg_cpf_incident = CPFbkg_in/factor
         if not background:
	    yy = 1.0 - CPFtot_corr
	    v[ yy < 1e-4 ] = False
	    yy[ yy < 1e-4 ] = 1e-4    # limit if yy gets very small or negative !!
	    CPFtot_in = (-1.0/alpha) * np.log(yy)
            obs_cpf_incident = CPFtot_in/specfactor
         

   except:
      print "ERROR: probably the effective counts per frame are > 1."
      print "WARNING: Continuing Setting COI factor = 1.0"
      obs_cpf_incident = obs_countsperframe
   
   # notify user that some points were flagged bad
   if v.all() != True: 
      ngood = len( np.where(v)[0] )
      print "WARNING uvotgetspec.coi_func(): Some data were ignored \n"+\
      "in the determination of the COI factor, since they exceeded the theoretical limit! "
      print "                              number of good points used = ",ngood
   
   # compute the coi-correction factor
   if not background: coi_factor    = (obs_cpf_incident - bkg_cpf_incident) / (obs_countsperframe - bkg_countsperframe)
   bg_coi_factor = (bkg_cpf_incident)/(bkg_countsperframe)
   
   # debug info
   if (chatter > 4) & (not background):
      print "bkg_countsperframe bkg_cpf_incident obs_countsperframe obs_cpf_incident bg_coi_factor coi_factor"
      for i in range(len(obs_cpf_incident)):
         print "%3i  %12.5f %12.5f %12.5f %12.5f %12.5f %12.5f" % (i,bkg_countsperframe[i],bkg_cpf_incident[i],\
	 obs_countsperframe[i],obs_cpf_incident[i],bg_coi_factor[i],coi_factor[i])
   
   # calibrate
   if chatter > 0: 
      if not background: print " coi_factor stats (min, mean, max): ",np.min(coi_factor),np.mean(coi_factor),np.max(coi_factor)
      print " bgcoi_factor stats (min, mean, max): ",np.min(bg_coi_factor),np.mean(bg_coi_factor),np.max(bg_coi_factor)
   
   # assume wave is monotonically increasing: 
   if not background: coi_func = interpolate.interp1d(wave[v],coi_factor[v],kind='nearest',bounds_error=False,fill_value=1.0 ) 
   coi_bg_func = interpolate.interp1d(wave,bg_coi_factor,kind='nearest',bounds_error=False,fill_value=1.0 )
   if debug:   return coi_func, coi_bg_func, (coi_factor,coi_bg_factor,factor,obs_cpf_incident,bkg_cpf_incident)
   elif background: return coi_bg_func 
   elif (not background): return coi_func

   
def plan_obs_using_mags(S2N=3.0,lentifilter=None,mag=None,bkgrate=0.16,coi=False, obsfile=None,grism='uv'):
   '''Tool to compute the grism exposure time needed to get a certain S/N in the 
   filterband given observed magnitude in lentifilter.
   
   Parameters
   ----------
   S2N : float
     signal to noise desired

   lentifilter : str, {'uvw2','uvm2','uvw1','u','b','v'}, optional if `obsfile` given
     lenticular filter in which a magnitude is available
   
   mag : float, optional if `obsfile` given
     measured magnitude in `lentifilter`.
     
   bkgrate : float
     the count rate in the background. This parameter determines 
     for weak spectra to a large extent what exposure time is required.
   
   coi : bool
     apply coincidence-loss correction ? *not yet implemented*
     
   obsfile : path, str, optional if `lentifilter`,`mag` given
     ascii filename with two columns wave, flux 
     or a fits file with the spectrum in the second extension
   
   grism : str, {'uv'}
   
   Returns
   -------
   An estimate of the required exposure time is printed
   
   Notes
   -----
   Lentifilter should be one of: uvw2, uvm2, uvw1, u, b, v
   
   Assumed source is faint - no coi (can later add coi)
      
   The exposure time will ramp up quickly once the target gets too faint. 
   The background in the clocked uv grism varies and can be lower, 
   like 0.06 depnding of where the spectrum is put on the detector. 
   So we could update this program at some point with the uv clocked 
   background variation in it. Typically background values are below 
   0.1 c/s/arcsec. Higher backgrounds are found in crowded fields.  
      
   If obsfile is given, then calculate the magnitudes using the 
   spectrum from the obsfile
       
   TO DO: V grism placeholder 
       
   - 16 April 2012, initial version, Paul Kuin 
   '''   
   import numpy as np
   import io
   import uvotmisc
   import uvotphot
   import pyfits
   
   if lentifilter == 'w1': lentifilter = 'uvw1'
   if lentifilter == 'w2': lentifilter = 'uvw2'
   if lentifilter == 'm2': lentifilter = 'uvm2'
   
   if (obsfile == None):
     # total lenticular filter effective area / FWHM (CALDB)
     lf_ea = [21.27, 10.89, 22.57, 50.32,62.65,21.44]
     # FWHM lenticular filter (Poole et al.,2008)
     delta_w = [769.,975.,785.,693.,498.,657.]
     if grism == 'uv': 
          disp_coef1 = 3.2
          # rough estimate grism effective area at lenticular filter
          gr_ea = [1.5, 7.0, 12.3, 16.3, 12.5, 6.5]
          # central wave lenticular filter = [5468.,4392,3465,2600,2246,1928.] 
     elif grism == 'v':
          disp_coef1 = 6.0
          # rough estimate grism effective area at lenticular filter
          gr_ea = [1.5, 7.0, 12.3, 16.3, 12.5, 6.5]
          # central wave lenticular filter = [5468.,4392,3465,2600,2246,1928.] 
          print "not yet implemented"
	  return
     else:
          print 'grism unknown'
	  return
	  	
     # check valid mag and filter     
     if mag == None:
         print "problem with input parameters: expected a magnitude"
     else:
         # convert to grism CR
         if lentifilter == 'v':
             factor = gr_ea[0]*disp_coef1/(lf_ea[0]*delta_w[0])
         elif lentifilter == 'b':	
             factor = gr_ea[1]*disp_coef1/(lf_ea[1]*delta_w[1])
         elif lentifilter == 'u':	
             factor = gr_ea[2]*disp_coef1/(lf_ea[2]*delta_w[2])
         elif lentifilter == 'uvw1':	
             factor = gr_ea[3]*disp_coef1/(lf_ea[3]*delta_w[3])
         elif lentifilter == 'uvw2':	
             factor = gr_ea[4]*disp_coef1/(lf_ea[4]*delta_w[4])
         elif lentifilter == 'uvm2':	
             factor = gr_ea[5]*disp_coef1/(lf_ea[5]*delta_w[5])
         else: factor = 32./(155620.1) # white-ish 	

      # convert mag to source count rate in filter using ZP
         zp = uvotphot.uvot_zeropoint(lentifilter+'_uvot',date=None,system='VEGA')
         src_cr =  10**( -0.4*(mag-zp) )
      
      # multiply by factor to get CR/pix in grism
      
         src_cr *= factor
            
      # add background for total rate, noise rate
         tot_cr = src_cr + bkgrate
         noise_cr_squared =  tot_cr + bkgrate 
      # compute exposure for given S2N 
         exposure = S2N**2 * noise_cr_squared / ( src_cr**2 ) 
         print "for a s/n = ",S2N,"  magnitude "+lentifilter+"=",mag," an exposure = ",exposure,"s is needed."
         print "assumed background count rate = ",bkgrate
         print "source count rate = ",src_cr
   else:
      try:
         hdu = pyfits.open(obsfile)
         wave = hdu[2].data['lambda']
	 flux = hdu[2].data['flux']
	 hdu.close()
      except:
         try: 	 
	    tab = uvotmisc.rdTab(obsfile)
	    wave = tab[:,0]
	    flux = tab[:,1]
	 except:
	    print "FATAL ERROR: problem reading "+obsfile   
	    return
      good = np.isfinite(flux)
      wave = wave[good]
      flux = flux[good]
      
      f = open('plan_obs_file.tmp','w')
      for i in range(len(wave)):
         f.write("%10.3f  %12.5e\n"%(wave[i],flux[i]))
      X = uvotphot.uvotmag_from_spectrum(specfile='plan_obs_file.tmp',)	 
	 	 
# end uvotgetspec.py  See Copyright notice in README file [when missing, copyright NPM Kuin, 2013, applies]. 