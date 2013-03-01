"""Handle network addresses and ranges

Tools for validating, parsing, and comparing network addresses, ranges,
and for querying whether a given address is within a set of ranges.

Address is an abstract class, of which IPv4 and IPv6 are subclasses,
which builds on top of the socket parsing of network addresses and
represents addresses directly as their integer values.

AddressRange is a general construct for specifying a contiguous block
of addresses, and does not connote a structure. Subnet adds CIDR
structure. AddressRanges are addable, and Subnets devolve into
AddressRanges for this purpose if there isn't a trivial overlap.

AddrList Replicates much of the behavior of John Hoffman's IP_List
data structures, if more simply. Ranges are stored in a strict
ordering, and addition of a new range will combine any now-contiguous
ranges.
"""

import struct
import socket
import bisect
import operator


class Address(long):
    """Integer representations of network addresses, building on the socket
    library.

    Subclass with number of bits and address family."""

    def __str__(self):
        """Use socket library formatting"""
        words = (0xffffffff & (self >> i)
                 for i in xrange(self.bits - 32, -1, -32))
        structdesc = ">{:d}L".format(self.bits / 32)
        return socket.inet_ntop(self.af, struct.pack(structdesc, *words))

    @classmethod
    def fromString(cls, address):
        """Create address from string

        Raises socket.error on failure"""
        shiftword = lambda x, y: (2 ** 32) * x + y
        structdesc = ">{:d}L".format(cls.bits / 32)
        return cls(reduce(shiftword, struct.unpack(structdesc,
                   socket.inet_pton(cls.af, address))))

    @classmethod
    def isString(cls, address):
        """Test if address is a valid string for address family"""
        try:
            socket.inet_pton(cls.af, address)
            return True
        except:
            return False

    def mask(self, n):
        """Return an address with the first n bits preserved and the
        rest zeroes out."""
        ones = (1 << self.bits) - 1
        return self.__class__(self & (ones << (self.bits - n)))


class IPv4(Address):
    bits = 32
    af = socket.AF_INET


class IPv6(Address):
    bits = 128
    af = socket.AF_INET6

ADDRESSTYPES = (IPv4, IPv6)


def addressToLong(address):
    for addrType in ADDRESSTYPES:
        if addrType.isString(address):
            return addrType.fromString(address)
    else:
        return None


class AddressRange(object):
    def __init__(self, start, end=None):
        if end is None:
            end = start
        assert start <= end
        self.start = start
        self.end = end
        self.family = type(start)

    def __str__(self):
        return '{}-{}'.format(self.start, self.end)

    def __contains__(self, x):
        if isinstance(x, AddressRange):
            return x.start >= self.start and x.end <= self.end
        return x >= self.start and x <= self.end

    def __add__(self, x):
        if isinstance(x, AddressRange):
            if x.start > self.end + 1:
                return (self, x)
            elif self.start > x.end + 1:
                return (x, self)
            else:
                return AddressRange(min(self.start, x.start),
                                    max(self.end, x.end))
        if x > self.end + 1:
            return (self, AddressRange(x))
        elif self.start > x + 1:
            return (AddressRange(x), self)
        else:
            return AddressRange(min(self.start, x), max(self.end, x))

    def __lt__(self, x):
        """True if there is at least one address above the range and below x"""
        if isinstance(x, AddressRange):
            return x.start > self.end + 1
        return x > self.end + 1

    def __gt__(self, x):
        """True if there is at least one address below the range and above x"""
        if isinstance(x, AddressRange):
            return self.start > x.end + 1
        return self.start > x + 1

    def __eq__(self, x):
        return self.start == x.start and self.end == x.end

    @classmethod
    def fromString(cls, iprange):
        start, dash, end = iprange.partition('-')
        startip = addressToLong(start)
        if end:
            endip = addressToLong(end)
            assert startip.bits == endip.bits
        else:
            endip = None
        return cls(startip, endip)


class Subnet(AddressRange):
    def __init__(self, address, cidr):
        self.address = address.mask(cidr)
        self.cidr = cidr

        self.start = self.address
        diff = (1 << (address.bits - cidr)) - 1
        self.end = address.__class__(self.start + diff)

        self.family = type(address)

    def __str__(self):
        return '{}/{:d}'.format(self.address, self.cidr)

    def __contains__(self, x):
        """Determine if an address or Subnet is subsumed by this Subset"""
        if isinstance(x, Subnet):
            return x.cidr > self.cidr and x.address in self
        return super(Subnet, self).__contains__(x)

    def __add__(self, x):
        """If a Subnet subsumes another range, keep the Subnet apparatus.
        If not, revert to AddressRange addition."""
        if x in self:
            return self
        elif self in x:
            return x
        else:
            return super(Subnet, self).__add__(x)

    @classmethod
    def fromCIDR(cls, netstring):
        ipstring, slash, cidrstring = netstring.partition('/')
        ip = addressToLong(ipstring)
        if cidrstring:
            cidr = int(cidrstring)
        else:
            cidr = ip.bits
        return cls(ip, cidr)


class AddrList(object):
    def __init__(self):
        self.ranges = {IPv4: [],
                       IPv6: []}

    def addIP(self, ip):
        self.addAddressRange(AddressRange(addressToLong(ip)))

    def addSubnet(self, subnet):
        self.addAddressRange(Subnet.fromCIDR(subnet))

    def addRange(self, iprange):
        self.addAddressRange(AddressRange.fromString(iprange))

    def addAddressRange(self, iprange):
        ranges = self.ranges[iprange.family]

        l = bisect.bisect_left(ranges, iprange)
        r = bisect.bisect_right(ranges, iprange)

        newseg = reduce(operator.add, ranges[l:r], iprange)
        ranges[l:r] = [newseg]

    def __contains__(self, address):
        ip = addressToLong(address)
        return any(ip in r for r in self.ranges[type(ip)])

    def set_intranet_addresses(self):
        self.addSubnet('127.0.0.1/8')
        self.addSubnet('10.0.0.0/8')
        self.addSubnet('172.16.0.0/12')
        self.addSubnet('192.168.0.0/16')
        self.addSubnet('169.254.0.0/16')
        self.addIP('::1')
        self.addSubnet('fe80::/16')
        self.addSubnet('fec0::/16')

    def set_ipv4_addresses(self):
        self.add('::ffff:0:0/96')

    def read_fieldlist(self, filename):
        """Read a list from a file in the format 'ip[/len] <whatever>'

        Leading whitespace is ignored, as are lines beginning with '#'
        """
        with open(filename, 'r') as f:
            for line in f:
                fields = line.split()
                if not fields or fields[0][0] == '#':
                    continue

                try:
                    self.addSubnet(fields[0])
                except:
                    print '*** WARNING *** could not parse IP range: ' + line

    def read_rangelist(self, filename):
        """Read a list from a file in the format 'whatever:whatever:ip[-ip]
        (not IPv6 compatible at all)"""
        with open(filename, 'r') as f:
            for line in f:
                fields = line.split()
                if not fields or fields[0][0] == '#':
                    continue

                try:
                    self.addRange(fields[0].split(':')[-1])
                except:
                    print '*** WARNING *** could not parse IP range: ' + line

ipv4addrmask = IPv6.fromString('::ffff:0:0')


def ipv6_to_ipv4(ip):
    unmasked = IPv4(IPv6.fromString(ip) ^ ipv4addrmask)
    if unmasked >> IPv4.bits:
        raise ValueError("not convertible to IPv4")
    return str(unmasked)

is_ipv4 = IPv4.isString


def to_ipv4(ip):
    if is_ipv4(ip):
        return ip
    return ipv6_to_ipv4(ip)


def is_valid_ip(ip):
    return (IPv4.isString(ip) or IPv6.isString(ip))
