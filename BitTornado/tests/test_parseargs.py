import unittest

from BitTornado.Application.parseargs import parseargs


class ParseArgsTest(unittest.TestCase):
    def test_parseargs(self):
        self.assertEqual(parseargs(('d', '--a', 'pq', 'e', '--b', '3', '--c',
                                    '4.5', 'f'),
                                   (('a', 'x', ''), ('b', 1, ''),
                                    ('c', 2.3, ''))),
                         ({'a': 'pq', 'b': 3, 'c': 4.5}, ['d', 'e', 'f']))
        self.assertEqual(parseargs([], [('a', 'x', '')]), ({'a': 'x'}, []))
        self.assertEqual(parseargs(['--a', 'x', '--a', 'y'], [('a', '', '')]),
                         ({'a': 'y'}, []))
        self.assertEqual(parseargs(['x'], [], 1, 2), ({}, ['x']))
        self.assertEqual(parseargs(['x', 'y'], [], 1, 2), ({}, ['x', 'y']))
        self.assertRaises(ValueError, parseargs, ['--a', 'x'], [])
        self.assertRaises(ValueError, parseargs, ['--a'], [('a', 'x', '')])
        self.assertRaises(ValueError, parseargs, [], [], 1, 2)
        self.assertRaises(ValueError, parseargs, ['x', 'y', 'z'], [], 1, 2)
        self.assertRaises(ValueError, parseargs, ['--a', '2.0'],
                          [('a', 3, '')])
        self.assertRaises(ValueError, parseargs, ['--a', 'z'],
                          [('a', 2.1, '')])

if __name__ == '__main__':
    unittest.main()
