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
    bits = None
    af = None

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
        except socket.error:
            return False

    def mask(self, nbits):
        """Return an address with the first n bits preserved and the
        rest zeroes out."""
        ones = (1 << self.bits) - 1
        return self.__class__(self & (ones << (self.bits - nbits)))


class IPv4(Address):
    """Integer representation of IPv4 network addresses, building on the
    socket library."""
    bits = 32
    af = socket.AF_INET


class IPv6(Address):
    """Integer representation of IPv6 network addresses, building on the
    socket library."""
    bits = 128
    af = socket.AF_INET6

ADDRESSTYPES = (IPv4, IPv6)


def addressToLong(address):
    """Generic function to translate any recognized addresses to their
    corresponding Address subclass instances."""
    for addrType in ADDRESSTYPES:
        if addrType.isString(address):
            return addrType.fromString(address)
    raise ValueError('Invalid address: {}'.format(address))


class AddressRange(object):     # pylint: disable=R0903
    """Range within a given address family that allows unions, comparisons,
    and checks for inclusion."""
    def __init__(self, start, end=None):
        """Create range of from start to end, or lift address into a
        range, if no end."""
        if end is None:
            end = start
        assert start <= end
        self.start = start
        self.end = end
        self.family = type(start)

    def __str__(self):
        return '{}-{}'.format(self.start, self.end)

    def __contains__(self, addr):
        if isinstance(addr, AddressRange):
            return addr.start >= self.start and addr.end <= self.end
        return addr >= self.start and addr <= self.end

    def __add__(self, addr):
        if isinstance(addr, AddressRange):
            if addr.start > self.end + 1:
                return (self, addr)
            elif self.start > addr.end + 1:
                return (addr, self)
            else:
                return AddressRange(min(self.start, addr.start),
                                    max(self.end, addr.end))
        if addr > self.end + 1:
            return (self, AddressRange(addr))
        elif self.start > addr + 1:
            return (AddressRange(addr), self)
        else:
            return AddressRange(min(self.start, addr), max(self.end, addr))

    def __lt__(self, addr):
        """True if there is at least one address above the range and below x"""
        if isinstance(addr, AddressRange):
            return addr.start > self.end + 1
        return addr > self.end + 1

    def __gt__(self, addr):
        """True if there is at least one address below the range and above x"""
        if isinstance(addr, AddressRange):
            return self.start > addr.end + 1
        return self.start > addr + 1

    def __eq__(self, addr):
        return self.start == addr.start and self.end == addr.end

    @classmethod
    def fromString(cls, iprange):
        """Parse address range of the form start-end"""
        start, _, end = iprange.partition('-')
        startip = addressToLong(start)
        if end:
            endip = addressToLong(end)
            assert startip.bits == endip.bits
        else:
            endip = None
        return cls(startip, endip)


class Subnet(AddressRange):
    """Address range that operates on the logic of CIDR blocks.

    If addition of new addresses breaks this logic, revert to AddressRange."""
    def __init__(self, address, cidr):
        self.address = address.mask(cidr)
        self.cidr = cidr

        start = self.address
        diff = (1 << (address.bits - cidr)) - 1
        end = address.__class__(start + diff)

        super(Subnet, self).__init__(start, end)

    def __str__(self):
        return '{}/{:d}'.format(self.address, self.cidr)

    def __contains__(self, addr):
        """Determine if an address or Subnet is subsumed by this Subset"""
        if isinstance(addr, Subnet):
            return addr.cidr > self.cidr and addr.address in self
        return super(Subnet, self).__contains__(addr)

    def __add__(self, addr):
        """If a Subnet subsumes another range, keep the Subnet apparatus.
        If not, revert to AddressRange addition."""
        if addr in self:
            return self
        elif self in addr:
            return addr
        else:
            return super(Subnet, self).__add__(addr)

    @classmethod
    def fromCIDR(cls, netstring):
        """Parse CIDR string of the form IP/CIDR"""
        ipstring, _, cidrstring = netstring.partition('/')
        addr = addressToLong(ipstring)
        if cidrstring:
            cidr = int(cidrstring)
        else:
            cidr = addr.bits
        return cls(addr, cidr)


class AddrList(object):
    """Collection of addresses with no constraints on contiguity,
    featuring insertion functions and inclusion tests."""
    def __init__(self):
        self.ranges = {IPv4: [],
                       IPv6: []}

    def addIP(self, addr):
        """Insert individual address string into list"""
        self.addAddressRange(AddressRange(addressToLong(addr)))

    def addSubnet(self, subnet):
        """Insert CIDR block string into list"""
        self.addAddressRange(Subnet.fromCIDR(subnet))

    def addRange(self, iprange):
        """Insert contiguous address range string into list"""
        self.addAddressRange(AddressRange.fromString(iprange))

    def addAddressRange(self, iprange):
        """Insert AddressRange into list, combining overlapping list
        elements into a minimal set of ranges."""
        ranges = self.ranges[iprange.family]

        left = bisect.bisect_left(ranges, iprange)
        right = bisect.bisect_right(ranges, iprange)

        newseg = reduce(operator.add, ranges[left:right], iprange)
        ranges[left:right] = [newseg]

    def __contains__(self, address):
        longip = addressToLong(address)
        return any(longip in r for r in self.ranges[type(longip)])

    def set_intranet_addresses(self):
        """Add addresses corresponding to reserved instranet blocks"""
        self.addSubnet('127.0.0.1/8')
        self.addSubnet('10.0.0.0/8')
        self.addSubnet('172.16.0.0/12')
        self.addSubnet('192.168.0.0/16')
        self.addSubnet('169.254.0.0/16')
        self.addIP('::1')
        self.addSubnet('fe80::/16')
        self.addSubnet('fec0::/16')

    def set_ipv4_addresses(self):
        """Add the block of IPv4 addresses in the IPv6 space"""
        self.addSubnet('::ffff:0:0/96')

    def read_fieldlist(self, filename):
        """Read a list from a file in the format 'ip[/len] <whatever>'

        Leading whitespace is ignored, as are lines beginning with '#'
        """
        with open(filename, 'r') as fieldlistfile:
            for line in fieldlistfile:
                fields = line.split()
                if not fields or fields[0][0] == '#':
                    continue

                try:
                    self.addSubnet(fields[0])
                except ValueError:
                    print '*** WARNING *** could not parse IP range: ' + line

    def read_rangelist(self, filename):
        """Read a list from a file in the format 'whatever:whatever:ip[-ip]
        (not IPv6 compatible at all)"""
        with open(filename, 'r') as rangelistfile:
            for line in rangelistfile:
                fields = line.split()
                if not fields or fields[0][0] == '#':
                    continue

                try:
                    self.addRange(fields[0].split(':')[-1])
                except ValueError:
                    print '*** WARNING *** could not parse IP range: ' + line

IPV4ADDRMASK = IPv6.fromString('::ffff:0:0')


def ipv6_to_ipv4(ip6):
    """Convert IPv6 address to IPv4 address, if possible"""
    unmasked = IPv4(IPv6.fromString(ip6) ^ IPV4ADDRMASK)
    if unmasked >> IPv4.bits:
        raise ValueError("not convertible to IPv4")
    return str(unmasked)

is_ipv4 = IPv4.isString     # pylint: disable=C0103


def to_ipv4(addr):
    """Convert IP string to IPv4 string"""
    if is_ipv4(addr):
        return addr
    return ipv6_to_ipv4(addr)


def is_valid_ip(addr):
    """Test if string is valid IPv4 or IPv6"""
    return IPv4.isString(addr) or IPv6.isString(addr)
