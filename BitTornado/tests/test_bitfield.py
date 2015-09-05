import unittest

from ..bitfield import Bitfield


class BitfieldTests(unittest.TestCase):
    def test_bitfield(self):
        """Unit test Bitfield"""
        self.assertRaises(ValueError, Bitfield, 7, b'ab')
        self.assertRaises(ValueError, Bitfield, 7, b'ab')
        self.assertRaises(ValueError, Bitfield, 9, b'abc')
        self.assertRaises(ValueError, Bitfield, 0, b'a')
        self.assertRaises(ValueError, Bitfield, 1, b'')
        self.assertRaises(ValueError, Bitfield, 7, b'')
        self.assertRaises(ValueError, Bitfield, 8, b'')
        self.assertRaises(ValueError, Bitfield, 9, b'a')
        self.assertRaises(ValueError, Bitfield, 7, b'\x01')
        self.assertRaises(ValueError, Bitfield, 9, b'\x00\x40')
        self.assertEqual(bytes(Bitfield(0, b'')), b'')
        self.assertEqual(bytes(Bitfield(1, b'\x80')), b'\x80')
        self.assertEqual(bytes(Bitfield(7, b'\x02')), b'\x02')
        self.assertEqual(bytes(Bitfield(8, b'\xFF')), b'\xFF')
        self.assertEqual(bytes(Bitfield(9, b'\x00\x80')), b'\x00\x80')
        testx = Bitfield(1)
        self.assertEqual(testx.numfalse, 1)
        testx[0] = 1
        self.assertEqual(testx.numfalse, 0)
        testx[0] = 1
        self.assertEqual(testx.numfalse, 0)
        self.assertEqual(bytes(testx), b'\x80')
        testx = Bitfield(7)
        self.assertEqual(len(testx), 7)
        testx[6] = 1
        self.assertEqual(testx.numfalse, 6)
        self.assertEqual(bytes(testx), b'\x02')
        testx = Bitfield(8)
        testx[7] = 1
        self.assertEqual(bytes(testx), b'\x01')
        testx = Bitfield(9)
        testx[8] = 1
        self.assertEqual(testx.numfalse, 8)
        self.assertEqual(bytes(testx), b'\x00\x80')
        testx = Bitfield(8, b'\xc4')
        self.assertEqual(len(testx), 8)
        self.assertEqual(testx.numfalse, 5)
        self.assertEqual(bytes(testx), b'\xc4')

if __name__ == '__main__':
    unittest.main()
