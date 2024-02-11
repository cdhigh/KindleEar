#!/usr/bin/env python3
# -*- coding:utf-8 -*-


import errno
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import suppress
from io import BytesIO
from threading import Thread
from PIL import Image
from calibre import fit_image, force_unicode
from calibre.constants import iswindows
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import atomic_rename
from calibre.utils.imghdr import what
from calibre.utils.resources import get_image_path as I
from polyglot.builtins import string_or_bytes

# Utilities {{{
class NotImage(ValueError):
    pass


def normalize_format_name(fmt):
    fmt = fmt.lower()
    if fmt == 'jpg':
        fmt = 'jpeg'
    return fmt


def get_exe_path(name):
    from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
    base = os.path.dirname(PDFTOHTML)
    if iswindows:
        name += '-calibre.exe'
    if not base:
        return name
    return os.path.join(base, name)


def load_jxr_data(data):
    return

# }}}

# png <-> gif {{{


def png_data_to_gif_data(data):
    img = Image.open(BytesIO(data)) if not isinstance(data, Image) else data
    buf = BytesIO()
    if img.mode in ('p', 'P'):
        transparency = img.info.get('transparency')
        if transparency is not None:
            img.save(buf, 'gif', transparency=transparency)
        else:
            img.save(buf, 'gif')
    elif img.mode in ('rgba', 'RGBA'):
        alpha = img.split()[3]
        mask = Image.eval(alpha, lambda a: 255 if a <=128 else 0)
        img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
        img.paste(255, mask)
        img.save(buf, 'gif', transparency=255)
    else:
        img = img.convert('P', palette=Image.ADAPTIVE)
        img.save(buf, 'gif')
    return buf.getvalue()


class AnimatedGIF(ValueError):
    pass


def gif_data_to_png_data(data, discard_animation=False):
    img = Image.open(BytesIO(data))
    if img.is_animated and not discard_animation:
        raise AnimatedGIF()
    buf = BytesIO()
    img.save(buf, 'png')
    return buf.getvalue()

# }}}

# Loading images {{{


def null_image():
    ' Create an invalid image. For internal use. '
    return Image()


def image_from_data(data):
    ' Create an image object from data, which should be a bytestring. '
    if isinstance(data, Image.Image):
        return data
    return Image.open(BytesIO(data))
    
def image_from_path(path):
    ' Load an image from the specified path. '
    with open(path, 'rb') as f:
        return image_from_data(f.read())


def image_from_x(x):
    ' Create an image from a bytestring or a path or a file like object. '
    if isinstance(x, str):
        return image_from_path(x)
    if hasattr(x, 'read'):
        return image_from_data(x.read())
    if isinstance(x, (bytes, Image)):
        return image_from_data(x)
    if isinstance(x, bytearray):
        return image_from_data(bytes(x))
    raise TypeError('Unknown image src type: %s' % type(x))


def image_and_format_from_data(data):
    ' Create an image object from the specified data which should be a bytestring and also return the format of the image '
    img = Image.open(BytesIO(data))
    return img, img.format
# }}}

# Saving images {{{


def image_to_data(img, compression_quality=95, fmt='JPEG', png_compression_level=9, jpeg_optimized=True, jpeg_progressive=False):
    '''
    Serialize image to bytestring in the specified format.

    :param compression_quality: is for JPEG and WEBP and goes from 0 to 100.
                                100 being lowest compression, highest image quality. For WEBP 100 means lossless with effort of 70.
    :param png_compression_level: is for PNG and goes from 0-9. 9 being highest compression.
    :param jpeg_optimized: Turns on the 'optimize' option for libjpeg which losslessly reduce file size
    :param jpeg_progressive: Turns on the 'progressive scan' option for libjpeg which allows JPEG images to be downloaded in streaming fashion
    '''
    fmt = fmt.upper()
    if fmt == 'GIF':
        return png_data_to_gif_data(img)
    else:
        data = BytesIO()
        img.save(data, fmt)
        return data.getvalue()

def save_image(img, path, **kw):
    ''' Save image to the specified path. Image format is taken from the file
    extension. You can pass the same keyword arguments as for the
    `image_to_data()` function. '''
    fmt = path.rpartition('.')[-1]
    kw['fmt'] = kw.get('fmt', fmt)
    with open(path, 'wb') as f:
        f.write(image_to_data(image_from_data(img), **kw))


def save_cover_data_to(
    data, path=None,
    bgcolor='#ffffff',
    resize_to=None,
    compression_quality=90,
    minify_to=None,
    grayscale=False,
    eink=False,
    letterbox=False,
    letterbox_color='#000000',
    data_fmt='jpeg'
):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Removes any transparency. If there is no transparency and no
    resize and the input and output image formats are the same, no changes are
    made.

    :param data: Image data as bytestring
    :param path: If None img data is returned, in JPEG format
    :param data_fmt: The fmt to return data in when path is None. Defaults to JPEG
    :param compression_quality: The quality of the image after compression.
        Number between 1 and 100. 1 means highest compression, 100 means no
        compression (lossless). When generating PNG this number is divided by 10
        for the png_compression_level.
    :param bgcolor: The color for transparent pixels. Must be specified in hex.
    :param resize_to: A tuple (width, height) or None for no resizing
    :param minify_to: A tuple (width, height) to specify maximum target size.
        The image will be resized to fit into this target size. If None the
        value from the tweak is used.
    :param grayscale: If True, the image is converted to grayscale,
        if that's not already the case.
    :param eink: If True, the image is dithered down to the 16 specific shades
        of gray of the eInk palette.
        Works best with formats that actually support color indexing (i.e., PNG)
    :param letterbox: If True, in addition to fit resize_to inside minify_to,
        the image will be letterboxed (i.e., centered on a black background).
    :param letterbox_color: If letterboxing is used, this is the background color
        used. The default is black.
    '''
    fmt = normalize_format_name(data_fmt if path is None else os.path.splitext(path)[1][1:])
    if isinstance(data, Image.Image):
        img = data
        changed = True
    else:
        img, orig_fmt = image_and_format_from_data(data)
        orig_fmt = normalize_format_name(orig_fmt)
        changed = (fmt.lower() != orig_fmt.lower())

    if resize_to or minify_to:
        width, height = img.size
        newWidth, newHeight = resize_to or minify_to
        if width > newWidth or height > newHeight: #按比率缩小，避免失真
            changed = True
            ratio = min(newWidth / width, newHeight / height)
            img = img.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)

    if (grayscale or eink) and img.mode != "L":
        img = img.convert("L")
        changed = True
    elif img.mode != 'RGB':
        img = img.convert('RGB')
        changed = True

    #if eink:
        # NOTE: Keep in mind that JPG does NOT actually support indexed colors, so the JPG algorithm will then smush everything back into a 256c mess...
        #       Thankfully, Nickel handles PNG just fine, and we potentially generate smaller files to boot, because they can be properly color indexed ;).
        #img = eink_dither_image(img)
        #changed = True
    if path is None:
        return image_to_data(img, fmt=fmt) if changed else data
    else:
        with open(path, 'wb') as f:
            f.write(image_to_data(img) if changed else data)
# }}}

# Overlaying images {{{


def blend_on_canvas(img, width, height, bgcolor='#ffffff'):
    ' Blend the `img` onto a canvas with the specified background color and size '
    return img

def overlay_image(img, canvas=None, left=0, top=0):
    ' Overlay the `img` onto the canvas at the specified position '
    return img


def texture_image(canvas, texture):
    ' Repeatedly tile the image `texture` across and down the image `canvas` '
    return img


def blend_image(img, bgcolor='#ffffff'):
    ' Used to convert images that have semi-transparent pixels to opaque by blending with the specified color '
    return img

def add_borders_to_image(img, left=0, top=0, right=0, bottom=0, border_color='#ffffff'):
    img = image_from_data(img)
    return img


def remove_borders_from_image(img, fuzz=None):
    return img
# }}}

# Cropping/scaling of images {{{


def resize_image(img, width, height):
    return img.resize((width, height), Image.Resampling.LANCZOS)
    #return img.scaled(int(width), int(height), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


def resize_to_fit(img, width, height):
    img = image_from_data(img)
    width, height = img.size
    newWidth, newHeight = resize_to
    ratio = min(newWidth / width, newHeight / height)
    img = img.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)
    return True, img


def clone_image(img):
    ''' Returns a shallow copy of the image. However, the underlying data buffer
    will be automatically copied-on-write '''
    return img.copy()


def scale_image(data, width=60, height=80, compression_quality=70, as_png=False, preserve_aspect_ratio=True):
    ''' Scale an image, returning it as either JPEG or PNG data (bytestring).
    Transparency is alpha blended with white when converting to JPEG. Is thread
    safe and does not require a QApplication. '''
    # We use Qt instead of ImageMagick here because ImageMagick seems to use
    # some kind of memory pool, causing memory consumption to sky rocket.
    img = image_from_data(data)
    owidth, oheight = img.size
    if preserve_aspect_ratio:
        ratio = min(width / owidth, height / oheight)
        img = img.resize((int(owidth * ratio), int(oheight * ratio)), Image.Resampling.LANCZOS)
    else:
        img = img.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)
    fmt = 'PNG' if as_png else 'JPEG'
    w, h = img.size
    return w, h, image_to_data(img, fmt=fmt)


def crop_image(img, x, y, width, height):
    '''
    Return the specified section of the image.

    :param x, y: The top left corner of the crop box
    :param width, height: The width and height of the crop box. Note that if
    the crop box exceeds the source images dimensions, width and height will be
    auto-truncated.
    '''
    img = image_from_data(img)
    width = min(width, img.width() - x)
    height = min(height, img.height() - y)
    return img.crop(int(x), int(y), int(width), int(height))

# }}}

# Image transformations {{{


def grayscale_image(img):
    return image_from_data(img).convert("L")

def set_image_opacity(img, alpha=0.5):
    return img


def flip_image(img, horizontal=False, vertical=False):
    img = image_from_data(img)
    if horizontal:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if vertical:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return img


def image_has_transparent_pixels(img):
    return False


def rotate_image(img, degrees):
    img = image_from_data(img)
    img = img.transpose(Image.Transpose.ROTATE_90)
    return img

def quantize_image(img, max_colors=256, dither=True, palette=''):
    return img


def eink_dither_image(img):
    return img

def optimize_jpeg(file_path):
    return


def optimize_png(file_path, level=7):
    return


def run_cwebp(file_path, lossless, q, m, metadata):
    return


def optimize_webp(file_path, q=100, m=6, metadata='all'):
    return


def encode_jpeg(file_path, quality=80):
    return

def encode_webp(file_path, quality=75, m=6, metadata='all'):
    return

