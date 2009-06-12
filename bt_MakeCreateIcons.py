#!/usr/bin/env python
# Written by John Hoffman

from time import strftime
from zlib import compress
from binascii import b2a_base64
from traceback import print_exc
import sys
from os.path import join
from BitTornado import version

icons = [ 'icon_bt.ico', 'icon_done.ico',
          'black.ico', 'blue.ico', 'green.ico', 'red.ico', 'white.ico', 'yellow.ico',
          'black1.ico', 'green1.ico', 'yellow1.ico', 'alloc.gif' ]

width = 60

normalstdout = sys.stdout
try:
    f = open('CreateIcons.py','w')
    sys.stdout = f

    print '# Generated from bt_MakeCreateIcons - '+strftime('%x %X')
    print '# '+version
    print ''
    print 'from binascii import a2b_base64'
    print 'from zlib import decompress'
    print 'from os.path import join'
    print ''

    print 'icons = {'
    for icon in icons:
        print '    "'+icon+'":'
        ff = open(join('icons',icon),'rb')
        d = b2a_base64(compress(ff.read())).strip()
        ff.close()
        while d:
            d1 = d[:width]
            d = d[width:]
            if d:
                extra = ' +'
            elif icon != icons[-1]:
                extra = ','
            else:
                extra = ''
            print '        "'+d1+'"'+extra
    print '}'
    print ''
    print 'def GetIcons():'
    print '    return icons.keys()'
    print ''
    print 'def CreateIcon(icon, savedir):'
    print '    try:'
    print '        f = open(join(savedir,icon),"wb")'
    print '        f.write(decompress(a2b_base64(icons[icon])))'
    print '        success = 1'
    print '    except:'
    print '        success = 0'
    print '    try:'
    print '        f.close()'
    print '    except:'
    print '        pass'
    print '    return success'

except:
    sys.stdout = normalstdout
    print_exc()
    try:
        ff.close()
    except:
        pass

sys.stdout = normalstdout
try:
    f.close()
except:
    pass


# here's the output code used

def GetIcons():
    return icons.keys()

def CreateIcon(icon, savedir):
    try:
        f = open(icon,'wb')
        f.write(decompress(a2b_base64(icons[icon])))
        success = 1
    except:
        success = 0
    try:
        f.close()
    except:
        pass
    return success
