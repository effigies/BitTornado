import unittest

from BitTornado.bitfield import Bitfield


class BitfieldTests(unittest.TestCase):
    def test_bitfield(self):
        """Unit test Bitfield"""
        self.assertRaises(ValueError, Bitfield, 7, 'ab')
        self.assertRaises(ValueError, Bitfield, 7, 'ab')
        self.assertRaises(ValueError, Bitfield, 9, 'abc')
        self.assertRaises(ValueError, Bitfield, 0, 'a')
        self.assertRaises(ValueError, Bitfield, 1, '')
        self.assertRaises(ValueError, Bitfield, 7, '')
        self.assertRaises(ValueError, Bitfield, 8, '')
        self.assertRaises(ValueError, Bitfield, 9, 'a')
        self.assertRaises(ValueError, Bitfield, 7, '\x01')
        self.assertRaises(ValueError, Bitfield, 9, '\x00\x40')
        self.assertEqual(str(Bitfield(0, '')), '')
        self.assertEqual(str(Bitfield(1, '\x80')), '\x80')
        self.assertEqual(str(Bitfield(7, '\x02')), '\x02')
        self.assertEqual(str(Bitfield(8, '\xFF')), '\xFF')
        self.assertEqual(str(Bitfield(9, '\x00\x80')), '\x00\x80')
        testx = Bitfield(1)
        self.assertEqual(testx.numfalse, 1)
        testx[0] = 1
        self.assertEqual(testx.numfalse, 0)
        testx[0] = 1
        self.assertEqual(testx.numfalse, 0)
        self.assertEqual(str(testx), '\x80')
        testx = Bitfield(7)
        self.assertEqual(len(testx), 7)
        testx[6] = 1
        self.assertEqual(testx.numfalse, 6)
        self.assertEqual(str(testx), '\x02')
        testx = Bitfield(8)
        testx[7] = 1
        self.assertEqual(str(testx), '\x01')
        testx = Bitfield(9)
        testx[8] = 1
        self.assertEqual(testx.numfalse, 8)
        self.assertEqual(str(testx), '\x00\x80')
        testx = Bitfield(8, '\xc4')
        self.assertEqual(len(testx), 8)
        self.assertEqual(testx.numfalse, 5)
        self.assertEqual(str(testx), '\xc4')

if __name__ == '__main__':
    unittest.main()
