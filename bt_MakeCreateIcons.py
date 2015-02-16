#!/usr/bin/env python
# Written by John Hoffman

import os
import time
import zlib
import binascii
import BitTornado

icons = ['icon_bt.ico', 'icon_done.ico',
         'black.ico', 'blue.ico', 'green.ico', 'red.ico', 'white.ico',
         'yellow.ico', 'black1.ico', 'green1.ico', 'yellow1.ico', 'alloc.gif']

width = 65

iconEncodings = []

for icon in icons:
    with open(os.path.join('icons', icon), 'rb') as ff:
        d = binascii.b2a_base64(zlib.compress(ff.read())).strip()

    width1 = width - len(icon) - 4
    key = '    "{}": "{}"\n'.format(icon, d[:width1])
    value = '\n'.join('    "{}"'.format(d[i:i + width])
                      for i in xrange(width1, len(d), width))
    iconEncodings.append(key + value)

with open('CreateIcons.py', 'w') as f:
    f.write("""# Generated from bt_MakeCreateIcons - {time}
# {version}

import os
import zlib
import binascii


icons = {{
{encodingDict}
}}


def GetIcons():
    return icons.keys()


def CreateIcon(icon, savedir):
    try:
        with open(os.path.join(savedir, icon), "wb") as f:
            f.write(zlib.decompress(binascii.a2b_base64(icons[icon])))
        return True
    except IOError:
        return False
""".format(time=time.strftime('%x %X'),
            version=BitTornado.version,
            encodingDict=',\n'.join(iconEncodings)))
