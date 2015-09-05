import unittest

from ..Meta.bencode import bencode, bdecode, Bencached


class CodecTests(unittest.TestCase):
    def test_bencode(self):
        """Test encoding of encodable and unencodable data structures"""
        self.assertEqual(bencode(4), b'i4e')
        self.assertEqual(bencode(0), b'i0e')
        self.assertEqual(bencode(-10), b'i-10e')
        self.assertEqual(bencode(12345678901234567890),
                         b'i12345678901234567890e')
        self.assertEqual(bencode(''), b'0:')
        self.assertEqual(bencode('abc'), b'3:abc')
        self.assertEqual(bencode('1234567890'), b'10:1234567890')
        self.assertEqual(bencode([]), b'le')
        self.assertEqual(bencode([1, 2, 3]), b'li1ei2ei3ee')
        self.assertEqual(bencode([['Alice', 'Bob'], [2, 3]]),
                         b'll5:Alice3:Bobeli2ei3eee')
        self.assertEqual(bencode({}), b'de')
        self.assertEqual(bencode({'age': 25, 'eyes': 'blue'}),
                         b'd3:agei25e4:eyes4:bluee')
        self.assertEqual(bencode({'spam.mp3': {'author': 'Alice',
                                               'length': 100000}}),
                         b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee')
        self.assertRaises(TypeError, bencode, {1: 'foo'})
        self.assertRaises(TypeError, bencode, {'foo': 1.0})

        cached = Bencached.cache({'age': 25})
        self.assertEqual(bencode(cached), cached.bencoded)

        self.assertEqual(bencode(''), bencode(b''))

    def test_bdecode(self):
        """Test decoding of valid and erroneous sample strings"""
        self.assertWarns(Warning, bdecode, b'0:0:')
        self.assertRaises(ValueError, bdecode, b'ie')
        self.assertRaises(ValueError, bdecode, b'i341foo382e')
        self.assertEqual(bdecode(b'i4e'), 4)
        self.assertEqual(bdecode(b'i0e'), 0)
        self.assertEqual(bdecode(b'i123456789e'), 123456789)
        self.assertEqual(bdecode(b'i-10e'), -10)
        self.assertRaises(ValueError, bdecode, b'i-0e')
        self.assertRaises(ValueError, bdecode, b'i123')
        self.assertRaises(ValueError, bdecode, b'')
        self.assertWarns(Warning, bdecode, b'i6easd')
        self.assertRaises(ValueError, bdecode, b'35208734823ljdahflajhdf')
        self.assertWarns(Warning, bdecode, b'2:abfdjslhfld')
        self.assertEqual(bdecode(b'0:'), '')
        self.assertEqual(bdecode(b'3:abc'), 'abc')
        self.assertEqual(bdecode(b'10:1234567890'), '1234567890')
        self.assertRaises(ValueError, bdecode, b'02:xy')
        self.assertRaises(ValueError, bdecode, b'l')
        self.assertEqual(bdecode(b'le'), [])
        self.assertWarns(Warning, bdecode, b'leanfdldjfh')
        self.assertEqual(bdecode(b'l0:0:0:e'), ['', '', ''])
        self.assertRaises(ValueError, bdecode, b'relwjhrlewjh')
        self.assertEqual(bdecode(b'li1ei2ei3ee'), [1, 2, 3])
        self.assertEqual(bdecode(b'l3:asd2:xye'), ['asd', 'xy'])
        self.assertEqual(bdecode(b'll5:Alice3:Bobeli2ei3eee'),
                         [['Alice', 'Bob'], [2, 3]])
        self.assertRaises(ValueError, bdecode, b'd')
        self.assertWarns(Warning, bdecode, b'defoobar')
        self.assertEqual(bdecode(b'de'), {})
        self.assertEqual(bdecode(b'd3:agei25e4:eyes4:bluee'),
                         {'age': 25, 'eyes': 'blue'})
        self.assertEqual(
            bdecode(b'd8:spam.mp3d6:author5:Alice6:lengthi100000eee'),
            {'spam.mp3': {'author': 'Alice', 'length': 100000}})
        self.assertRaises(ValueError, bdecode, b'd3:fooe')
        self.assertRaises(ValueError, bdecode, b'di1e0:e')
        self.assertRaises(ValueError, bdecode, b'd1:b0:1:a0:e')
        self.assertRaises(ValueError, bdecode, b'd1:a0:1:a0:e')
        self.assertRaises(ValueError, bdecode, b'i03e')
        self.assertRaises(ValueError, bdecode, b'l01:ae')
        self.assertRaises(ValueError, bdecode, b'9999:x')
        self.assertRaises(ValueError, bdecode, b'l0:')
        self.assertRaises(ValueError, bdecode, b'd0:0:')
        self.assertRaises(ValueError, bdecode, b'd0:')

if __name__ == '__main__':
    unittest.main()
