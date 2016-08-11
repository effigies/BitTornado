import unittest
import random
import math

from ..primitives import FixedLengthBytes, SixBytes, TwentyBytes, \
    UnsignedInt, UnsignedShort


class FixedLengthTests(unittest.TestCase):
    def test_fixedlengthbytes(self):
        self.assertRaises(NotImplementedError, FixedLengthBytes)
        self.assertRaises(NotImplementedError, FixedLengthBytes, b'')

    def test_sixbytes(self):
        self.assertRaises(ValueError, SixBytes, b'')
        self.assertEqual(SixBytes(), b'\x00' * 6)
        self.assertEqual(SixBytes(b'abcdef'), b'abcdef')

    def test_twentybytes(self):
        self.assertRaises(ValueError, TwentyBytes, b'')
        self.assertEqual(TwentyBytes(), b'\x00' * 20)
        self.assertEqual(TwentyBytes(b'a' * 20), b'a' * 20)


class UnsignedIntTests(unittest.TestCase):
    def test_create(self):
        self.assertRaises(OverflowError, UnsignedInt, -1)
        for i in range(1, 30):
            UnsignedInt('1' * i)
            UnsignedInt.from_bytes(b'\x01' * i, 'big')

    def test_bytelength(self):
        for _ in range(10):
            x = UnsignedInt(random.randrange(2**128))
            self.assertGreaterEqual(x.byte_length() * 8, x.bit_length())
            self.assertLess((x.byte_length() - 1) * 8, x.bit_length())

    def test_bytestring(self):
        for _ in range(10):
            x = UnsignedInt(random.randrange(2**128))
            self.assertEqual(len(x.bytestring()), x.byte_length())
            self.assertEqual(int.from_bytes(x.bytestring(), 'big'), x)


class BoundedMixin:
    def test_create(self):
        self.assertRaises(OverflowError, self.cls, -1)
        self.assertRaises(OverflowError, self.cls, 2 ** self.cls.bits)
        for _ in range(10):
            self.cls(random.randrange(2 ** self.cls.bits))

    def test_bytelength(self):
        for _ in range(10):
            x = self.cls(random.randrange(2 ** self.cls.bits))
            self.assertEqual(x.byte_length(), int(math.ceil(x.bits / 8.0)))
            self.assertLessEqual(x.bit_length(), x.bits)

    def test_bytestring(self):
        for _ in range(10):
            x = self.cls(random.randrange(2 ** self.cls.bits))
            self.assertEqual(self.cls.from_bytes(x.bytestring(), 'big'), x)


class UnsignedShortTests(unittest.TestCase, BoundedMixin):
    cls = UnsignedShort


class OddBoundedTests(unittest.TestCase, BoundedMixin):
    class cls(UnsignedInt):
        bits = 7
