import unittest
import random

from BitTornado.Network.NetworkAddress import Address, IP, IPv4, IPv6, \
    AddressRange, Subnet, AddrList, to_ipv4, is_valid_ip

IPV4MAX = 0xffffffff
IPV6MAX = 0xffffffffffffffffffffffffffffffff


class AddressTests(unittest.TestCase):
    def test_bare(self):
        with self.assertRaises(NotImplementedError):
            Address()

    def test_ip(self):
        default = IP()
        self.assertIsInstance(default, IPv4)
        self.assertEqual(default, 0)
        v4home = IP('127.0.0.1')
        v6home = IP('::ffff:127.0.0.1')
        self.assertIsInstance(v4home, IPv4)
        self.assertIsInstance(v6home, IPv6)
        self.assertEqual(v4home.to(IPv6), v6home)
        self.assertEqual(v6home.to(IPv4), v4home)
        self.assertNotEqual(IPv6(v4home), v6home)
        with self.assertRaises(OverflowError):
            IPv4(v6home)

    def test_ipv4(self):
        min32bit = 0
        max32bit = IPV4MAX
        self.assertEqual(IPv4(min32bit), min32bit)
        self.assertEqual(IPv4(max32bit), max32bit)
        with self.assertRaises(OverflowError):
            IPv4(min32bit - 1)
        with self.assertRaises(OverflowError):
            IPv4(max32bit + 1)

        homestr = '127.0.0.1'
        homebytes = b'\x7f\x00\x00\x01'
        homeip = IPv4(homestr)
        self.assertEqual(str(homeip), homestr)
        self.assertEqual(homeip, IPv4.from_bytes(homebytes, 'big'))
        self.assertEqual(homeip.to_bytes(4, 'big'), homebytes)

        bad4strings = ('127.0.0.256', 'NotAnAddress', '::ffff:127.0.0.1')
        for string in bad4strings:
            with self.assertRaises(ValueError):
                IPv4(string)

    def test_ipv6(self):
        min128bit = 0
        max128bit = IPV6MAX
        self.assertEqual(IPv6(min128bit), min128bit)
        self.assertEqual(IPv6(max128bit), max128bit)
        with self.assertRaises(OverflowError):
            IPv4(min128bit - 1)
        with self.assertRaises(OverflowError):
            IPv4(max128bit + 1)

        homestr = '::1'
        homebytes = bytes([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
        homeip = IPv6(homestr)
        self.assertEqual(str(homeip), homestr)
        self.assertEqual(homeip, IPv6.from_bytes(homebytes, 'big'))
        self.assertEqual(homeip.to_bytes(16, 'big'), homebytes)

        bad6strings = ('127.0.0.1', 'NotAnAddress', '::ffff::')
        for string in bad6strings:
            with self.assertRaises(ValueError):
                IPv6(string)

    def test_funcs(self):
        # Generated IPs should be valid
        for _ in range(10):
            self.assertTrue(is_valid_ip(str(IPv4(random.randint(0, IPV4MAX)))))
            self.assertTrue(is_valid_ip(str(IPv6(random.randint(0, IPV6MAX)))))
        badips = ('NotAnAddress', '127.0.0.256', '::ff::', '::fffg:0:0', '-1')
        for badip in badips:
            self.assertFalse(is_valid_ip(badip))

        for _ in range(10):
            rand4 = random.randint(0, IPV4MAX)
            str4 = str(IPv4(rand4))
            str6 = str(IPv6(rand4 + IP.v4mask))
            self.assertEqual(str4, to_ipv4(str4))
            self.assertEqual(str4, to_ipv4(str6))


class AddressRangeTests(unittest.TestCase):
    def test_range(self):
        for i in range(5):
            rng = AddressRange(IP(i))
            self.assertEqual(rng.start, i)
            self.assertEqual(rng.end, i)
            self.assertEqual(rng.family, IPv4)
            for j in range(5):
                if i > j:
                    with self.assertRaises(AssertionError):
                        AddressRange(IP(i), IP(j))
                else:
                    rng = AddressRange(IP(i), IP(j))
                    self.assertEqual(rng.start, i)
                    self.assertEqual(rng.end, j)
                    self.assertEqual(rng.family, IPv4)
        with self.assertRaises(AssertionError):
            rng.end = IP()

        v4rangestr = '0.0.0.0-255.255.255.255'
        v6rangestr = '::-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'
        v4range = AddressRange.from_string(v4rangestr)
        v6range = AddressRange.from_string(v6rangestr)
        self.assertEqual(str(v4range), v4rangestr)
        self.assertEqual(str(v6range), v6rangestr)
        self.assertEqual(v4range, AddressRange(IPv4(0), IPv4(IPV4MAX)))
        self.assertEqual(v6range, AddressRange(IPv6(0), IPv6(IPV6MAX)))

    def test_ordering(self):
        def expect(A1, A2, B1, B2):
            assert A2 >= A1 and B2 >= B1
            lt = A2 + 1 < B1
            eq = A1 == B1 and A2 == B2
            gt = A1 > B2 + 1
            a_in_b = B1 <= A1 and A2 <= B2
            b_in_a = A1 <= B1 and B2 <= A2
            return (lt, eq, gt, a_in_b, b_in_a)

        def test(A, B):
            return (A < B, A == B, A > B, A in B, B in A)

        y, z = 3, 6
        B = AddressRange(IPv4(y), IPv4(z))
        for w in range(10):
            for x in range(w, 10):
                A = AddressRange(IPv4(w), IPv4(x))
                self.assertEqual(test(A, B), expect(w, x, y, z))
                self.assertEqual(test(B, A), expect(y, z, w, x))

    def test_addition(self):
        range1 = AddressRange.from_string('127.0.0.0-127.0.0.255')
        range2 = AddressRange.from_string('127.0.1.0-127.0.1.255')
        range3 = AddressRange.from_string('127.0.1.1-127.0.1.255')
        range4 = AddressRange.from_string('127.0.0.128-127.0.1.128')
        range5 = AddressRange.from_string('127.0.0.0-127.0.1.255')

        # Adjacent ranges
        self.assertEqual(range1 + range2, range5)
        self.assertEqual(range2 + range1, range5)
        # Disjoint ranges
        self.assertEqual(range1 + range3, (range1, range3))
        self.assertEqual(range3 + range1, (range1, range3))
        # Nested ranges
        self.assertEqual(range2 + range3, range2)
        self.assertEqual(range3 + range2, range2)
        # Overlapping ranges
        self.assertEqual(range1 + range4,
                         AddressRange.from_string('127.0.0.0-127.0.1.128'))
        self.assertEqual(range2 + range4,
                         AddressRange.from_string('127.0.0.128-127.0.1.255'))


class SubnetTests(unittest.TestCase):
    def test_subnet(self):
        randomaddr4 = IPv4(random.randint(0, IPV4MAX))
        randomaddr6 = IPv6(random.randint(0, IPV6MAX))
        for cidr in range(128):
            if cidr <= 32:
                teststr4 = '{!s}/{:d}'.format(randomaddr4, cidr)
                subnet4 = Subnet(randomaddr4, cidr)
                self.assertIn(randomaddr4, subnet4)
                self.assertEqual(Subnet.from_string(teststr4), subnet4)
            teststr6 = '{!s}/{:d}'.format(randomaddr6, cidr)
            subnet6 = Subnet(randomaddr6, cidr)
            self.assertIn(randomaddr6, subnet6)
            self.assertEqual(Subnet.from_string(teststr6), subnet6)

        self.assertIn(Subnet(randomaddr4, 24), Subnet(randomaddr4, 16))
        self.assertIn(Subnet(randomaddr6, 96), Subnet(randomaddr6, 64))

    def test_addition(self):
        range1 = Subnet.from_string('127.0.0.0/24')
        range2 = Subnet.from_string('127.0.1.0/24')
        range3 = Subnet.from_string('127.0.0.0/23')

        # Adjacent ranges
        self.assertEqual(range1 + range2, range3)
        self.assertEqual(range2 + range1, range3)
        self.assertIsInstance(range1 + range2, AddressRange)
        self.assertFalse(isinstance(range1 + range2, Subnet))


class TestAddrList(unittest.TestCase):
    def test_addrlist(self):
        alist = AddrList()
        self.assertSetEqual(set(alist.ranges.keys()), {IPv4, IPv6})

        alist.add_ip('127.0.0.1')
        self.assertIn('127.0.0.1', alist)
        self.assertNotIn('127.0.0.0', alist)
        alist.add_range('127.0.0.2-127.0.0.255')
        self.assertListEqual(
            alist.ranges[IPv4],
            [AddressRange.from_string('127.0.0.1-127.0.0.255')])
        alist.add_ip('127.0.0.0')
        self.assertListEqual(alist.ranges[IPv4],
                             [Subnet.from_string('127.0.0.0/24')])
        alist.add_subnet('127.0.2.0/23')
        self.assertListEqual(alist.ranges[IPv4],
                             [Subnet.from_string('127.0.0.0/24'),
                              Subnet.from_string('127.0.2.0/23')])
        # Unify disjoint ranges with single addition
        sub = Subnet.from_string('127.0.1.0/24')
        self.assertNotIn(sub.start, alist)
        self.assertNotIn(sub.end, alist)
        alist.add_addressrange(sub)
        self.assertListEqual(alist.ranges[IPv4],
                             [Subnet.from_string('127.0.0.0/22')])


if __name__ == '__main__':
    unittest.main()
