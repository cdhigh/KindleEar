#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from PIL import Image

from calibre.utils.imghdr import what
from StringIO import StringIO

def identify_data(data):
    '''
    Identify the image in data. Returns a 3-tuple
    (width, height, format)
    or raises an Exception if data is not an image.
    '''
    if not isinstance(data, StringIO):
        data = StringIO(data)    
    img = Image.open(data)
    width, height = img.size
    fmt = img.format
    return (width, height, fmt)
    
    
def rescale_image(data, maxsizeb=4000000, dimen=None, 
                png2jpg=False, graying=True, reduceto=(600,800)):
    '''
    Convert image setting all transparent pixels to white and changing format
    to JPEG. Ensure the resultant image has a byte size less than
    maxsizeb.

    If dimen is not None, generate a thumbnail of
    width=dimen, height=dimen or width, height = dimen (depending on the type
    of dimen)

    Returns the image as a bytestring.
    '''
    if not isinstance(data, StringIO):
        data = StringIO(data)
    img = Image.open(data)
    width, height = img.size
    fmt = img.format
    if graying and img.mode != "L":
        img = img.convert("L")
    
    reducewidth, reduceheight = reduceto
    
    if dimen is not None:
        if hasattr(dimen, '__len__'):
            width, height = dimen
        else:
            width = height = dimen
        img.thumbnail((width, height))
        if png2jpg and fmt == 'PNG':
            fmt = 'JPEG'
        data = StringIO()
        img.save(data, fmt)
    elif width > reducewidth or height > reduceheight:
        ratio = min(float(reducewidth) / float(width), float(reduceheight) / float(height))
        img = img.resize((int(width * ratio), int(height * ratio)), Image.ANTIALIAS)
        if png2jpg and fmt == 'PNG':
            fmt = 'JPEG'
        data = StringIO()
        img.save(data, fmt)
    elif png2jpg and fmt == 'PNG':
        data = StringIO()
        img.save(data, 'JPEG')
    else:
        data = StringIO()
        img.save(data, fmt)
    
    return data.getvalue()

def mobify_image(data):
    'Convert PNG images to GIF as the idiotic Kindle cannot display some PNG'
    fmt = what(None, data)

    if fmt == 'png':
        if not isinstance(data, StringIO):
            data = StringIO(data)
        im = Image.open(data)
        data = StringIO()
        im.save(data, 'GIF')
        data = data.getvalue()
    return data
