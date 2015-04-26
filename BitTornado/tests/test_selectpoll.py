import unittest

from BitTornado.Network.selectpoll import remove, insert


class PollListTests(unittest.TestCase):
    def test_remove(self):
        x = [2, 4, 6]
        remove(x, 2)
        self.assertEqual(x, [4, 6])
        x = [2, 4, 6]
        remove(x, 4)
        self.assertEqual(x, [2, 6])
        x = [2, 4, 6]
        remove(x, 6)
        self.assertEqual(x, [2, 4])
        x = [2, 4, 6]
        remove(x, 5)
        self.assertEqual(x, [2, 4, 6])
        x = [2, 4, 6]
        remove(x, 1)
        self.assertEqual(x, [2, 4, 6])
        x = [2, 4, 6]
        remove(x, 7)
        self.assertEqual(x, [2, 4, 6])
        x = [2, 4, 6]
        remove(x, 5)
        self.assertEqual(x, [2, 4, 6])
        x = []
        remove(x, 3)
        self.assertEqual(x, [])

    def test_insert(self):
        x = [2, 4]
        insert(x, 1)
        self.assertEqual(x, [1, 2, 4])
        x = [2, 4]
        insert(x, 3)
        self.assertEqual(x, [2, 3, 4])
        x = [2, 4]
        insert(x, 5)
        self.assertEqual(x, [2, 4, 5])
        x = [2, 4]
        insert(x, 2)
        self.assertEqual(x, [2, 4])
        x = [2, 4]
        insert(x, 4)
        self.assertEqual(x, [2, 4])
        x = [2, 3, 4]
        insert(x, 3)
        self.assertEqual(x, [2, 3, 4])
        x = []
        insert(x, 3)
        self.assertEqual(x, [3])

if __name__ == '__main__':
    unittest.main()
