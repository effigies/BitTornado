import unittest

from BitTornado.Storage.PieceBuffer import PieceBuffer
import array


class PieceBufferTests(unittest.TestCase):
    def test_buffer(self):
        teststring = b'teststringofsomelength'
        shorterstring = b'shorterstring'

        x = PieceBuffer()
        x.append(teststring)

        # Basic functionality
        self.assertEqual(len(x), len(teststring))
        self.assertEqual(x[:], array.array('B', teststring))
        self.assertEqual(x[0], teststring[0])
        self.assertEqual(x[1:-1], array.array('B', teststring[1:-1]))

        # Optimization
        self.assertIs(x.buf, x[:])
        self.assertIs(x.buf, x[:len(teststring)])

        # Bounds checking
        with self.assertRaises(IndexError):
            x[-len(teststring) * 2]
        with self.assertRaises(IndexError):
            x[len(teststring) * 2]

        # Test range of [a:b] combinations
        bounds = [-10, -5, -2, -1, 0, 1, 2, 5, 10]
        for start in bounds:
            for stop in bounds:
                self.assertEqual(x[start:stop], x.buf[start:stop])

        # Re-initializing PieceBuffer retains buf attribute
        # but acts empty
        x.init()
        self.assertEqual(len(x), 0)
        self.assertEqual(x[:], array.array('B'))
        self.assertEqual(x.buf, array.array('B', teststring))
        with self.assertRaises(IndexError):
            x[0]

        # Test equal behavior despite distinct buffer contents
        y = PieceBuffer()
        x.append(shorterstring)
        y.append(shorterstring)
        self.assertEqual(x.length, y.length)

        # Bounds checking
        with self.assertRaises(IndexError):
            x[len(shorterstring)]
        with self.assertRaises(IndexError):
            y[len(shorterstring)]
        with self.assertRaises(IndexError):
            x[-len(shorterstring) - 1]
        with self.assertRaises(IndexError):
            y[-len(shorterstring) - 1]

        # Test range of [a:b] combinations
        bounds = [-10, -5, -2, -1, 0, 1, 2, 5, 10]
        for start in bounds:
            for stop in bounds:
                self.assertEqual(x[start:stop], y[start:stop])

    def test_pool(self):
        # Test two PieceBuffers are not the same
        a = PieceBuffer()
        b = PieceBuffer()
        self.assertIsNot(b, a)

        # Test PieceBuffer reuse
        a.release()
        c = PieceBuffer()
        self.assertIs(c, a)

        # Test double-release warning
        c.release()
        self.assertWarns(RuntimeWarning, c.release)

        # Test re-initialization
        d = PieceBuffer()
        self.assertIs(d, a)
        d.append(b'test')
        d.release()
        d = PieceBuffer()
        self.assertEqual(len(d), 0)
        self.assertEqual(d[:], array.array('B'))
        self.assertEqual(d.buf, array.array('B', b'test'))

if __name__ == '__main__':
    unittest.main()
