import unittest
import operator as ops
import random

from .. import Bitfield


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

    def test_bitwise_ops(self):
        zeros = Bitfield(8, b'\x00')    # 0 0 0 0  0 0 0 0
        ones = Bitfield(8, b'\xff')     # 1 1 1 1  1 1 1 1
        aa = Bitfield(8, b'\xaa')       # 1 0 1 0  1 0 1 0
        fives = Bitfield(8, b'\x55')    # 0 1 0 1  0 1 0 1

        rands = tuple(Bitfield(8, random.randrange(256).to_bytes(1, 'big'))
                      for _ in range(10))

        bitfields = (zeros, ones, aa, fives) + rands
        inverses = ((ones, zeros), (aa, fives))

        # Invert
        for bf_a, bf_b in inverses:
            self.assertEqual(~bf_a, bf_b)
            self.assertEqual(bf_a, ~bf_b)

        # Tautologies
        for bitfield in bitfields:
            # Double inversion
            self.assertEqual(~~bitfield, bitfield)

            # Bitwise AND
            # Identity
            self.assertEqual(bitfield & ones, bitfield)
            self.assertEqual(bitfield & b'\xff', bitfield)
            self.assertEqual(bitfield & 0xff, bitfield)
            # Zero
            self.assertEqual(bitfield & zeros, zeros)
            self.assertEqual(bitfield & b'\x00', zeros)
            self.assertEqual(bitfield & 0x00, zeros)
            # Inverses
            self.assertEqual(bitfield & ~bitfield, zeros)

            # Bitwise OR
            # Identity
            self.assertEqual(bitfield | zeros, bitfield)
            self.assertEqual(bitfield | b'\x00', bitfield)
            self.assertEqual(bitfield | 0x00, bitfield)
            # Zero
            self.assertEqual(bitfield | ones, ones)
            self.assertEqual(bitfield | b'\xff', ones)
            self.assertEqual(bitfield | 0xff, ones)
            # Inverses
            self.assertEqual(bitfield | ~bitfield, ones)

            # Bitwise XOR
            # Identity
            self.assertEqual(bitfield ^ zeros, bitfield)
            self.assertEqual(bitfield ^ b'\x00', bitfield)
            self.assertEqual(bitfield ^ 0x00, bitfield)
            # Inversion
            self.assertEqual(bitfield ^ ones, ~bitfield)
            self.assertEqual(bitfield ^ b'\xff', ~bitfield)
            self.assertEqual(bitfield ^ 0xff, ~bitfield)
            self.assertEqual(bitfield ^ ~bitfield, ones)

        # Commutativity
        for bf_a in bitfields:
            for bf_b in bitfields:
                self.assertEqual(bf_a & bf_b, bf_b & bf_a)
                self.assertEqual(bf_a | bf_b, bf_b | bf_a)
                self.assertEqual(bf_a ^ bf_b, bf_b ^ bf_a)

        # Breakage
        for op in (ops.and_, ops.or_, ops.xor):
            self.assertRaises(ValueError, op, ones, Bitfield(9))
            self.assertRaises(ValueError, op, ones, b'\xff\xff')
            self.assertRaises(ValueError, op, ones, 258)

if __name__ == '__main__':
    unittest.main()
