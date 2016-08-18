import unittest
import random

from ..collections import TypedList, TypedDict, OrderedSet


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
