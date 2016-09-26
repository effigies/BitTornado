import unittest
import random

from ..collections import TypedList, TypedDict, DictSet, OrderedSet, SplitList
from ...Meta.bencode import bencode, bdecode
from ...Meta.Info import MetaInfo


class APITest(object):
    """API test mixin - Requires that all attributes of `baseclass` be
    present in `thisclass`"""
    baseclass = None
    thisclass = None
    initargs = ()
    initkwargs = {}

    def test_apisuperset(self):
        for attr in dir(self.baseclass):
            self.assertTrue(hasattr(self.thisclass, attr))

    def setUp(self):
        self.base = self.baseclass(*self.initargs, **self.initkwargs)
        self.this = self.thisclass(*self.initargs, **self.initkwargs)


class ComparableAPITest(APITest):
    """Comparable API test mixin - Requires that `thisclass` objects be
    testable for equality with `baseclass` objects, and that the methods and
    functions in `method_tests` and `function_tests` have the same effect
    on and produce the same output from both objects.

    `method_tests` is a list of (method_name, args, kwargs) that are
    run sequentially.
    `function_tests` is a list of (function, args, kwargs) that are run
    sequentially.
    """
    method_tests = []
    function_tests = []

    def setUp(self):
        super().setUp()
        self.assertEqual(self.base, self.this)

    def test_methods(self):
        for attr, args, kwargs in self.method_tests:
            with self.subTest(attr=attr):
                x = getattr(self.base, attr)(*args, **kwargs)
                y = getattr(self.this, attr)(*args, **kwargs)
                self.assertEqual(self.base, self.this)
                self.assertEqual(x, y)

    def test_functions(self):
        for func, args, kwargs in self.function_tests:
            with self.subTest(func=func.__name__):
                x = func(self.base, *args, **kwargs)
                y = func(self.this, *args, **kwargs)
                self.assertEqual(self.base, self.this)
                self.assertEqual(x, y)


class CopyAPITest(ComparableAPITest):
    """Mixin to test object copying and modifying methods on copies of objects

    Mostly useful when undoing is non-trivial
    """
    copy_tests = []

    def test_copy(self):
        bcopy = self.base.copy()
        tcopy = self.this.copy()
        self.assertEqual(bcopy, tcopy)
        self.assertIsNot(tcopy, self.this)
        self.assertEqual(type(tcopy), type(self.this))

    def test_copymethods(self):
        for attr, args, kwargs in self.copy_tests:
            with self.subTest(attr=attr):
                bcopy = self.base.copy()
                tcopy = self.this.copy()
                x = getattr(bcopy, attr)(*args, **kwargs)
                y = getattr(tcopy, attr)(*args, **kwargs)
                self.assertEqual(bcopy, tcopy)
                self.assertEqual(x, y)


class TypedListAPITest(CopyAPITest, unittest.TestCase):
    baseclass = list
    thisclass = TypedList

    init_args = "abcdef"
    method_tests = [('append',    ('g',),     {}),
                    ('pop',       (-1,),      {}),
                    ('insert',    (1, 'q'),   {}),
                    ]


class TypedDictAPITest(CopyAPITest, unittest.TestCase):
    baseclass = dict
    thisclass = TypedDict


class DictSetTest(CopyAPITest, unittest.TestCase):
    baseclass = set
    thisclass = DictSet
    initargs = ("abcdef",)
    comparator = set("defghi")
    subset = set("abc")
    superset = set("abcdefg")

    method_tests = [('add',                     ('g',),         {}),
                    ('discard',                 ('g',),         {}),
                    ('difference',              (comparator,),  {}),
                    ('intersection',            (comparator,),  {}),
                    ('symmetric_difference',    (comparator,),  {}),
                    ('issubset',                (comparator,),  {}),
                    ('issubset',                (subset,),      {}),
                    ('issubset',                (superset,),    {}),
                    ('issuperset',              (comparator,),  {}),
                    ('issuperset',              (subset,),      {}),
                    ('issuperset',              (superset,),    {}),
                    ('union',                   (comparator,),  {}),
                    ]

    copy_tests = [('difference_update',             (comparator,),  {}),
                  ('symmetric_difference_update',   (comparator,),  {}),
                  ('intersection_update',           (comparator,),  {}),
                  ('update',                        (comparator,),  {}),
                  ]

    def test_bencoding(self):
        orig = DictSet(('a', 'b', 'c'))
        self.assertEqual(bencode(orig), b'd1:ai1e1:bi1e1:ci1ee')
        self.assertEqual(DictSet(bdecode(bencode(orig))), orig)

    def test_comparisons(self):
        # Equality should imply the following:
        self.assertTrue(self.this <= self.base)
        self.assertTrue(self.this >= self.base)
        self.assertTrue(self.base <= self.this)
        self.assertTrue(self.base >= self.this)

        tcopy = self.this.copy()
        x = tcopy.pop()

        self.assertTrue(x not in tcopy)  # value removed
        self.assertTrue(x in self.this)  # original unaffected

        # Test comparisons in DictSet
        self.assertEqual(len(tcopy), len(self.base) - 1)
        self.assertTrue(tcopy < self.this)
        self.assertTrue(tcopy <= self.this)
        self.assertTrue(self.this >= tcopy)
        self.assertTrue(self.this > tcopy)

        bcopy = self.base.copy()
        bcopy.pop()

        # Check that comparisons with normal sets work as expected
        self.assertTrue(self.base > tcopy)
        self.assertTrue(self.base >= tcopy)
        self.assertTrue(bcopy < self.this)
        self.assertTrue(bcopy <= self.this)


class SplitListTest(unittest.TestCase):
    def test_null(self):
        self.assertEqual(SplitList(), SplitList([]))
        self.assertEqual(SplitList(), SplitList(''))
        self.assertEqual(SplitList(), SplitList(['']))

    def test_announcelist(self):
        cls = MetaInfo.AnnounceList
        self.assertEqual(cls(), cls(''))
        self.assertEqual(cls(), cls([]))
        self.assertEqual(cls('a,b,c'), [['a', 'b', 'c']])
        self.assertEqual(cls('a|b|c'), [['a'], ['b'], ['c']])
        self.assertEqual(cls('a,b|c'), [['a', 'b'], ['c']])


class OrderedSetTest(unittest.TestCase):
    def test_orderedpop(self):
        """Test that removing arbitrary values from an ordered set is
        the same as removing from a sorted list"""
        for _ in range(10):
            vals = random.sample(range(100), 10)
            oset = OrderedSet(vals)
            sorted_vals = sorted(vals)

            while len(oset) > 0:
                n = random.randrange(len(oset))
                oset.pop(n)
                sorted_vals.pop(n)
                self.assertEqual(sorted(oset), sorted_vals)
