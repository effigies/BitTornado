"""Handle network ranges

Tools for validating, parsing, and comparing network address ranges,
and for querying whether a given address is within a set of ranges.

AddressRange is a general construct for specifying a contiguous block
of addresses, and does not connote a structure. Subnet adds CIDR
structure. AddressRanges are addable, and Subnets devolve into
AddressRanges for this purpose if there isn't a trivial overlap.

AddrList replicates much of the behavior of John Hoffman's IP_List
data structures, if more simply. Ranges are stored in a strict
ordering, and addition of a new range will combine any now-contiguous
ranges.
"""

import bisect
import operator
from functools import reduce
from ..Types import IP, IPv4, IPv6


class AddressRange(object):     # pylint: disable=R0903
    """Range within a given address family that allows unions, comparisons,
    and checks for inclusion.

    Strict greater/less-than comparisons are True when two ranges cannot be
    combined because there is at least one address separating the two. This
    allows a new range to be quickly inserted into a sorted list of ranges,
    combining when possible.
    """
    def __init__(self, start, end=None):
        """Create range of from start to end, or lift address into a
        range, if no end."""
        if end is None:
            end = start
        self.family = type(start)
        self.setrange(start, end)

    def setrange(self, start, end):
        """Set AddressRange bounds"""
        assert isinstance(start, self.family)
        assert isinstance(end, self.family)
        assert start <= end
        self._start, self._end = start, end

    @property
    def start(self):
        """First IP in range"""
        return self._start

    @start.setter
    def start(self, val):
        """Set first IP in range"""
        self.setrange(val, self._end)

    @property
    def end(self):
        """Last IP in range"""
        return self._end

    @end.setter
    def end(self, val):
        """Set last IP in range"""
        self.setrange(self._start, val)

    def __str__(self):
        return '{}-{}'.format(self._start, self._end)

    def __contains__(self, addr):
        if isinstance(addr, AddressRange):
            return self._start <= addr.start and addr.end <= self._end
        return self._start <= addr <= self._end

    def __add__(self, addr):
        if not isinstance(addr, AddressRange):
            addr = AddressRange(addr)

        if self < addr:
            return (self, addr)
        elif self > addr:
            return (addr, self)
        elif addr in self:
            return self
        elif self in addr:
            return addr
        else:
            return AddressRange(min(self._start, addr.start),
                                max(self._end, addr.end))

    def __lt__(self, addr):
        """True if there is at least one address above the range and below
        addr"""
        if isinstance(addr, AddressRange):
            addr = addr.start
        return self._end + 1 < addr

    def __gt__(self, addr):
        """True if there is at least one address below the range and above
        addr"""
        if isinstance(addr, AddressRange):
            addr = addr.end
        return self._start > addr + 1

    def __eq__(self, addr):
        return self._start == addr.start and self._end == addr.end

    @classmethod
    def from_string(cls, iprange):
        """Parse address range of the form start-end"""
        start, _, end = iprange.partition('-')
        startip = IP(start)
        if end:
            endip = IP(end)
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

    def __add__(self, addr):
        """If a Subnet subsumes another range, keep the larger Subnet. If not,
        revert to AddressRange addition."""
        if addr in self:
            return self
        elif self in addr:
            return addr
        else:
            return super(Subnet, self).__add__(addr)

    @classmethod
    def from_string(cls, netstring):
        """Parse CIDR string of the form IP/CIDR"""
        ipstring, _, cidr = netstring.partition('/')
        addr = IP(ipstring)
        return cls(addr, int(cidr) if cidr else addr.bits)


class AddrList(object):
    """Collection of addresses with no constraints on contiguity,
    featuring insertion functions and inclusion tests."""
    def __init__(self):
        self.ranges = {IPv4: [], IPv6: []}

    def add_ip(self, addr):
        """Insert individual address string into list"""
        self.add_addressrange(AddressRange(IP(addr)))

    def add_subnet(self, subnet):
        """Insert CIDR block string into list"""
        self.add_addressrange(Subnet.from_string(subnet))

    def add_range(self, iprange):
        """Insert contiguous address range string into list"""
        self.add_addressrange(AddressRange.from_string(iprange))

    def add_addressrange(self, iprange):
        """Insert AddressRange into list, combining overlapping list
        elements into a minimal set of ranges."""
        ranges = self.ranges[iprange.family]

        left = bisect.bisect_left(ranges, iprange)
        right = bisect.bisect_right(ranges, iprange)

        newseg = reduce(operator.add, ranges[left:right], iprange)
        ranges[left:right] = [newseg]

    def __contains__(self, address):
        if not isinstance(address, IP):
            address = IP(address)
        return any(address in r for r in self.ranges[type(address)])

    def set_intranet_addresses(self):
        """Add addresses corresponding to reserved instranet blocks"""
        self.add_subnet('127.0.0.1/8')
        self.add_subnet('10.0.0.0/8')
        self.add_subnet('172.16.0.0/12')
        self.add_subnet('192.168.0.0/16')
        self.add_subnet('169.254.0.0/16')
        self.add_ip('::1')
        self.add_subnet('fe80::/16')
        self.add_subnet('fec0::/16')

    def set_ipv4_addresses(self):
        """Add the block of IPv4 addresses in the IPv6 space"""
        self.add_subnet('::ffff:0:0/96')

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
                    self.add_subnet(fields[0])
                except ValueError:
                    print('*** WARNING *** could not parse IP range: ', line)

    def read_rangelist(self, filename):
        """Read a list from a file in the format 'whatever:whatever:ip[-ip]
        (not IPv6 compatible at all)"""
        with open(filename, 'r') as rangelistfile:
            for line in rangelistfile:
                fields = line.split()
                if not fields or fields[0][0] == '#':
                    continue

                try:
                    self.add_range(fields[0].split(':')[-1])
                except ValueError:
                    print('*** WARNING *** could not parse IP range: ', line)


def to_ipv4(addr):
    """Convert IP string to IPv4 string"""
    return str(IP(addr).to(IPv4))


def is_valid_ip(addr):
    """Test if string is valid IPv4 or IPv6"""
    try:
        IP(addr)
        return True
    except (ValueError, OverflowError, TypeError):
        return False
