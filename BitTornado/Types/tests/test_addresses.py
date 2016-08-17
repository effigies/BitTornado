import unittest

from .. import Address, IP, IPv4, IPv6

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


if __name__ == '__main__':
    unittest.main()
