# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import gst
from flumotion.common import errors
from flumotion.component import feedcomponent

class Firewire(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['video', 'audio'],
                                                    pipeline)
        self.volume = self.get_pipeline().get_by_name("setvolume")
        
    def setVolume(self, value):
        """
        @param value: float between 0.0 and 4.0
        """
        self.debug("Setting volume to %f" % (value))

        self.volume.set_property('volume', value)

                                       
# See comments in gstdvdec.c for details on the dv format.

def createComponent(config):
    width = config.get('width', 240)
    height = config.get('height', int(720.0/width*576)) # assuming PAL :-/
    scaled_width = config.get('scaled_width', width)
    is_square = config.get('is_square', False)
    framerate = config.get('framerate', 12.5)

    scale_correction = width - scaled_width

    if 12.5 < framerate <= 25:
        drop_factor = 1
    elif 6.3 < framerate <= 12.5:
        drop_factor = 2
    elif 3.2 < framerate <= 6.3:
        drop_factor = 4
    else:
        drop_factor = 8

    if is_square:
        square_pipe = ',pixel-aspect-ratio=(fraction)1/1'
    else:
        square_pipe = ''

    # the point of width correction is to get to a multiple of 8 for width
    # so codecs are happy; it's unrelated to the aspect ratio correction
    # to get to 4:3 or 16:9
    if scale_correction > 0:
        # videobox in 0.8.8 has a stride problem outputting AYUV with odd width
        # I420 works fine, but is slower when overlay is used

        pad_pipe = '! ffmpegcolorspace ! videobox right=-%d ! video/x-raw-yuv,format=(fourcc)I420 ' % scale_correction
    else:
        pad_pipe = ''

    # Scale down to half size and back again to lose interlacing
    # artifacts.
    if height > 288:
        interlaced_height = 576
    else:
        interlaced_height = 288
        
    # FIXME: might be nice to factor out dv1394src ! dvdec so we can replace it
    # with videotestsrc of the same size and PAR, so we can unittest the pipeline
    if gst.gst_version < (0,9):
        template = ('dv1394src ! dvdec name=dec drop-factor=%(df)d'
                    '    ! video/x-raw-yuv,format=(fourcc)YUY2'
                    '    ! videorate ! videoscale'
                    '    ! video/x-raw-yuv,width=%(sw)s,height=%(ih)s%(sq)s'
                    '    ! videoscale'
                    '    ! video/x-raw-yuv,width=%(sw)s,height=%(h)s,framerate=%(fr)f,format=(fourcc)YUY2'
                    '    %(pp)s'
                    '    ! @feeder::video@'
                    '  dec. ! audio/x-raw-int ! volume name=setvolume'
                    '    ! level name=volumelevel signal=true ! audiorate'
                    '    ! @feeder::audio@'
                    % dict(df=drop_factor, ih=interlaced_height,
                           sq=square_pipe, pp=pad_pipe,
                           sw=scaled_width, h=height, fr=framerate))
    else:
        template = ('dv1394src ! dvdemux name=demux'
                    '  demux. ! dvdec drop-factor=%(df)d'
                    '    ! video/x-raw-yuv,format=(fourcc)YUY2'
                    '    ! videorate ! videoscale'
                    '    ! video/x-raw-yuv,width=%(sw)s,height=%(ih)s%(sq)s'
                    '    ! videoscale'
                    '    ! video/x-raw-yuv,width=%(sw)s,height=%(h)s,framerate=%(fr)f,format=(fourcc)YUY2'
                    '    %(pp)s'
                    '    ! @feeder::video@'
                    '  demux. ! audio/x-raw-int ! volume name=setvolume'
                    '    ! level name=volumelevel message=true ! audiorate'
                    '    ! @feeder::audio@'
                    % dict(df=drop_factor, ih=interlaced_height,
                           sq=square_pipe, pp=pad_pipe,
                           sw=scaled_width, h=height, fr=framerate))
    
    component = Firewire(config['name'], template)
    
    if gst.gst_version < (0,9):
        from flumotion.component.effects.volume import volume
        comp_level = component.get_pipeline().get_by_name('volumelevel')
        vol = volume.Volume('inputVolume', comp_level)
        component.addEffect(vol)

    return component
