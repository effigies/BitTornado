# Written by John Hoffman
# see LICENSE.txt for license information

import socket
from bisect import bisect, insort

def _int_to_bitstring(x, bits=8):
    return ''.join(str((x >> i) & 0x1) for i in xrange(bits-1,-1,-1))

charbinmap = [_int_to_bitstring(n) for n in xrange(256)]

def to_bitfield_ipv4(ip):
    return ''.join(charbinmap[ord(i)] for i in socket.inet_aton(ip))

def to_bitfield_ipv6(ip):
    return ''.join(charbinmap[ord(i)]
                    for i in socket.inet_pton(socket.AF_INET6,ip))

ipv4addrmask = to_bitfield_ipv6('::ffff:0:0')[:96]

class IP_List:
    def __init__(self, entrylist=None):
        self.ipv4list = []
        self.ipv6list = []
        if entrylist:
            for ip, depth in entrylist:
                self._append(ip,depth)
            self.ipv4list.sort()
            self.ipv6list.sort()


    def __nonzero__(self):
        return bool(self.ipv4list or self.ipv6list)


    def _append(self, ip, depth = 256):
        if ip.find(':') < 0:        # IPv4
            self.ipv4list.append(to_bitfield_ipv4(ip)[:depth])
        else:
            b = to_bitfield_ipv6(ip)
            if b.startswith(ipv4addrmask):
                self.ipv4list.append(b[96:][:depth-96])
            else:
                self.ipv6list.append(b[:depth])

    def append(self, ip, depth = 256):
        if ip.find(':') < 0:        # IPv4
            insort(self.ipv4list,to_bitfield_ipv4(ip)[:depth])
        else:
            b = to_bitfield_ipv6(ip)
            if b.startswith(ipv4addrmask):
                insort(self.ipv4list,b[96:][:depth-96])
            else:
                insort(self.ipv6list,b[:depth])


    def includes(self, ip):
        if not (self.ipv4list or self.ipv6list):
            return False
        if ip.find(':') < 0:        # IPv4
            b = to_bitfield_ipv4(ip)
        else:
            b = to_bitfield_ipv6(ip)
            if b.startswith(ipv4addrmask):
                b = b[96:]
        if len(b) > 32:
            l = self.ipv6list
        else:
            l = self.ipv4list
        for map in l[bisect(l,b)-1:]:
            if b.startswith(map):
                return True
            if map > b:
                return False
        return False


    def read_fieldlist(self, filename):
        """Read a list from a file in the format 'ip[/len] <whatever>'
        
        Leading whitespace is ignored, as are lines beginning with '#'
        """
        with open(filename, 'r') as f:
            for line in f:
                fields = line.split()
                if not fields or fields[0][0] == '#':
                    continue

                ip, slash, depth = fields[0].partition('/')

                try:
                    if depth != '':
                        self._append(ip,int(depth))
                    else:
                        self._append(ip)
                except:
                    print '*** WARNING *** could not parse IP range: '+line
        self.ipv4list.sort()
        self.ipv6list.sort()


    def set_intranet_addresses(self):
        self.append('127.0.0.1',8)
        self.append('10.0.0.0',8)
        self.append('172.16.0.0',12)
        self.append('192.168.0.0',16)
        self.append('169.254.0.0',16)
        self.append('::1')
        self.append('fe80::',16)
        self.append('fec0::',16)

    def set_ipv4_addresses(self):
        self.append('::ffff:0:0',96)

def ipv6_to_ipv4(ip):
    ip = to_bitfield_ipv6(ip)
    if not ip.startswith(ipv4addrmask):
        raise ValueError, "not convertible to IPv4"
    ip = ip[-32:]
    x = '.'.join(str(int(ip[i:i+8],2)) for i in xrange(0,32,8))

def to_ipv4(ip):
    if is_ipv4(ip):
        return ip
    return ipv6_to_ipv4(ip)

def is_ipv4(ip):
    try:
        socket.inet_aton(ip)
        return True
    except:
        return False

def is_valid_ip(ip):
    if not ip:
        return False
    if is_ipv4(ip):
        return True
    try:
        socket.inet_pton(socket.AF_INET6,ip)
        return True
    except:
        return False
