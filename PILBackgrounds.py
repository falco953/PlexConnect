#!/usr/bin/env python

import re
import sys
import io
import urllib
import urllib2
import urlparse
import posixpath
import math
import ntpath
import traceback

import os.path
import unicodedata

from Debug import * 

try:
    from PIL import Image, ImageFilter, ImageFont, ImageDraw
    __isPILinstalled = True
except ImportError:
    __isPILinstalled = False

# Background Arguments:
#
# resolution            -       720p or 1080p, aTV based
# blurRadius            -       setting for blur radius
# gradientTemplate      -       image to lay over fanart
# titleText             -       main text
# subtitleText          -       second line Text
# titleSize             -       title size in px
# subtitleSize          -       subtitle size in px
# textColor             -       text color (FFFFFFF)
# align                 -       horizontal textalign (left, center, right)
# valign                -       vertical textalign (top, middle, bottom)
# offsetx               -       x position + offsetx px
# offsety               -       y position + offsety px
# lineheight            -       space between title and subtitle
# blurStart             -       % for blur start (0-100)
# blurEnd               -       % for blur end (0-100)
# statusText            -       text for top right (overlay view)
#

def generate(PMS_uuid, url, authtoken, resolution, blurRadius, gradientTemplate, titleText, subtitleText, titleSize, subtitleSize, textColor, align, valign, offsetx, offsety, lineheight, blurStart, blurEnd, statusText):
    cachepath = sys.path[0]+"/assets/fanartcache"
    stylepath = sys.path[0]+"/assets/thumbnails"

    # Create cache filename
    id = re.search('/library/metadata/(?P<ratingKey>\S+)/art/(?P<fileId>\S+)', url)
    if id:
        # assumes URL in format "/library/metadata/<ratingKey>/art/fileId>"
        id = id.groupdict()
        cachefile = urllib.quote_plus(PMS_uuid +"_"+ id['ratingKey'] +"_"+ id['fileId'] +"_"+ resolution +"_"+ blurRadius) + titleText + subtitleText + gradientTemplate + ".jpg"
    else:
        fileid = posixpath.basename(urlparse.urlparse(url).path)
        cachefile = urllib.quote_plus(PMS_uuid +"_"+ fileid +"_"+ resolution +"_"+ blurRadius) + titleText + subtitleText + gradientTemplate + ".jpg"  # quote: just to make sure...
    
    # Already created?
    dprint(__name__, 1, 'Check for Cachefile.')  # Debug
    if os.path.isfile(cachepath+"/"+cachefile):
        dprint(__name__, 1, 'Cachefile  found.')  # Debug
        return "/fanartcache/"+cachefile
    
    # No! Request Background from PMS
    dprint(__name__, 1, 'No Cachefile found. Generating Background.')  # Debug
    try:
        dprint(__name__, 1, 'Getting Remote Image.')  # Debug
        xargs = {}
        if authtoken:
            xargs['X-Plex-Token'] = authtoken
        request = urllib2.Request(url, None, xargs)
        response = urllib2.urlopen(request).read()
        background = Image.open(io.BytesIO(response))
    except urllib2.URLError as e:
        dprint(__name__, 0, 'URLError: {0} // url: {1}', e.reason, url)
        return "/thumbnails/Background_blank_" + resolution + ".jpg"
    except urllib2.HTTPError as e:
        dprint(__name__, 0, 'HTTPError: {0} {1} // url: {2}', str(e.code), e.msg, url)
        return "/thumbnails/Background_blank_" + resolution + ".jpg"
    except IOError as e:
        dprint(__name__, 0, 'IOError: {0} // url: {1}', str(e), url)
        return "/thumbnails/Background_blank_" + resolution + ".jpg"
    
    blurRadius = int(blurRadius)
    
    # Get gradient template
    dprint(__name__, 1, 'Merging Layers.')  # Debug
    if resolution == '1080':
        width = 1920
        height = 1080
        blurStart = (1080/100) * int(blurStart)
        blurEnd = (1080/100) * int(blurEnd)
        blurRegion = (0, blurStart, 1920, blurEnd)
        # FT: get Background based on last Parameter
        layer = Image.open(stylepath + "/" + gradientTemplate + "_1080.png")
    else:
        width = 1280
        height = 720
        blurStart = (720/100) * int(blurStart)
        blurEnd = (720/100) * int(blurEnd)
        blurRegion = (0, blurStart, 1280, blurEnd)
        blurRadius = int(blurRadius / 1.5)
        layer = Image.open(stylepath + "/" + gradientTemplate + "_720.png")
    
    # Set background resolution and merge layers
    try:
        bgWidth, bgHeight = background.size
        dprint(__name__,1 ,"Background size: {0}, {1}", bgWidth, bgHeight)
        dprint(__name__,1 , "aTV Height: {0}, {1}", width, height)
        
        if bgHeight != height:
            background = background.resize((width, height), Image.ANTIALIAS)
            dprint(__name__,1 , "Resizing background")
        
        if blurRadius != 0:
            dprint(__name__,1 , "Blurring Lower Region")
            imgBlur = background.crop(blurRegion)
            imgBlur = imgBlur.filter(ImageFilter.GaussianBlur(blurRadius))
            background.paste(imgBlur, blurRegion)

        background.paste(layer, ( 0, 0), layer)

        background = textToImage(stylepath, background, resolution, titleText, titleSize, textColor, align, valign, offsetx, offsety)

        if subtitleText != "":
            offsety = int(offsety) + int(lineheight)
            background = textToImage(stylepath, background, resolution, subtitleText, subtitleSize, textColor, align, valign, offsetx, offsety)

        # Handle 1080 / atv3 Text
        statusSize = 20
        statusX = 80
        statusY = 25

        if resolution == '1080':
            statusSize = fullHDtext(statusSize)
            statusX = fullHDtext(statusX)
            statusY = fullHDtext(statusY)
    
        if statusText != "":
            background = textToImage(stylepath, background, resolution, statusText, statusSize, textColor, "right", "top", statusX, statusY)

        # Save to Cache
        background.save(cachepath+"/"+cachefile)
    except:
        dprint(__name__, 0, 'Error - Failed to generate background image.\n{0}', traceback.format_exc())
        return "/thumbnails/Background_blank_" + resolution + ".jpg"
    
    dprint(__name__, 1, 'Cachefile  generated.')  # Debug
    return "/fanartcache/"+cachefile



# HELPERS

def textToImage(stylepath, im, resolution, textToWrite, fontsize, color, align, valign, offsetX, offsetY):
    # Set Font
    font = stylepath + "/font.ttf"

    # Set Color From Hex Value
    if is_hex(color):
        textcolor = color
        textcolor = tuple(int(textcolor[i:i+len(textcolor)/3], 16) for i in range(0, len(textcolor), len(textcolor)/3))
    
    else: # Default Color
        textcolor = (255, 255, 255)

    # Handle 1080 / atv3 Text

    if resolution == '1080':
        layerWidth = 1920
        layerHeight = 1080
        fontsize = fullHDtext(fontsize)
        offsetX = fullHDtext(offsetX)
        offsetY = fullHDtext(offsetY)
    else:
        layerWidth = 1280
        layerHeight = 720
        fontsize = int(fontsize)
        offsetX = int(offsetX)
        offsetY = int(offsetY)

    # Text & TypeSpace
    text = unicode(urllib.unquote(textToWrite), 'utf-8').replace('+',' ').strip()
    draw = ImageDraw.Draw(im)
    width, height = draw.textsize(text, ImageFont.truetype(font, fontsize))


    # Anchor and Offset X
    if align == "right":
        offsetx = layerWidth - width - offsetX
    elif align == "center":
        offsetx = (layerWidth - width ) / 2
    elif align == "left":
        offsetx = int(offsetX)

    # Anchor and Offset Y
    if valign == "bottom":
        offsety = layerHeight - offsetY
    elif valign == "middle":
        offsety = (layerHeight - height ) / 2
    elif valign == "top":
        offsety = int(offsetY)



    # Write
    dprint(__name__,1 ,"Text: {0} size: {1} offsetX: {2} offsetY: {3} font: {4} color: {5}", text, fontsize,offsetx,offsety, font, textcolor)

    draw.text((int(offsetx), int(offsety)), text , font=ImageFont.truetype(font, fontsize), fill=textcolor)
    return im



def fullHDtext(number):
    number = int(number)*1080/720
    return number

def is_hex(s):
    hex_digits = set("0123456789abcdefABCDEF")
    for char in s:
        if not (char in hex_digits):
            return False
    return True



def isPILinstalled():
    return __isPILinstalled



if __name__=="__main__":
    url = "http://thetvdb.com/banners/fanart/original/95451-23.jpg"
    res = generate('uuid', url, 'authtoken', '1080')
    res = generate('uuid', url, 'authtoken', '720')
    dprint(__name__, 0, "Background: {0}", res)
