import collections
import urllib


class CopyMixin(object):
    def copy(self):
        return self.__class__(self)


def normalize(arg, targettype, targetmap):
    """Coerce arg to targettype, optionally using targetmap to provide
    a conversion functions for source types."""
    argtype = type(arg)
    if targettype is not None and argtype is not targettype:
        if isinstance(targettype, tuple) and \
                isinstance(arg, collections.Iterable):
            return tuple(normalize(subarg, subtype, targetmap)
                         for subarg, subtype in zip(arg, targettype))
        elif targetmap is not None and argtype in targetmap:
            return targetmap[argtype](arg)
        else:
            return targettype(arg)
    return arg


class TypedList(CopyMixin, list):
    """TypedList() -> new empty list
    TypedList(iterable) -> new list initialized from iterable's items

    TypedList is a list that can constrain the types of its elements
    through the following class variables (if None, have no effect):

        valtype     type                Type of values
        valmap      {type: type -> valtype}
                                        Mapping from source val type to
                                        function to coerce val to valtype

    The values of elements may be constrained with the valconst class
    method:
        valconst    valtype -> bool     Constraint for valid values
    """
    valtype = valmap = None
    valconst = staticmethod(lambda arg: True)
    error = True

    def _normalized(method):
        """Decorator that applies type constraints and transformations
        to list operations"""
        def new_method(self, *args):
            new_args = ()
            idx_methods = ('__setitem__', 'insert')
            seq_methods = ('__init__', 'extend', '__add__', '__iadd__')
            expect_seq = method.__name__ in seq_methods
            if method.__name__ in idx_methods and args:
                new_args, args = (args[:1], args[1:])
                expect_seq = isinstance(new_args[0], slice)

            for arg in args:
                arg = iter(arg) if expect_seq else (arg,)
                try:
                    arg = list(normalize(sub, self.valtype, self.valmap)
                               for sub in arg)
                except (TypeError, ValueError):
                    raise TypeError("Values must be coercible to type '{}'"
                                    "".format(self.valtype.__name__))

                accept = []
                for val in arg:
                    if self.valconst(val):
                        accept.append(val)
                    elif self.error:
                        raise ValueError('Value rejected: {!r}'.format(val))

                new_args += (accept,) if expect_seq else tuple(accept)

            return method(self, *new_args)
        # Cleans up pydoc
        new_method.__name__ = method.__name__
        new_method.__doc__ = method.__doc__
        return new_method

    __init__ = _normalized(list.__init__)
    __setitem__ = _normalized(list.__setitem__)
    append = _normalized(list.append)
    extend = _normalized(list.extend)
    insert = _normalized(list.insert)
    __add__ = _normalized(list.__add__)
    __iadd__ = _normalized(list.__iadd__)


class SplitList(TypedList):
    splitchar = ' '

    valtype = str    # Typically
    valconst = bool  # Reject null values
    error = False    # Don't fail on null values

    def __init__(self, *args):
        super(SplitList, self).__init__()
        if len(args) > 1:
            raise TypeError("{}() takes at most 1 argument ({:d} given)"
                            "".format(self.__class__, len(args)))
        if args:
            self.extend(*args)

    def extend(self, vals):
        if isinstance(vals, type(self.splitchar)):
            vals = vals.split(self.splitchar)
        super(SplitList, self).extend(vals)


class TypedDict(CopyMixin, dict):
    """
    TypedDict() -> new empty dictionary
    TypedDict(mapping) -> new dictionary initialized from a mapping object's
        (key, value) pairs
    TypedDict(iterable) -> new dictionary initialized as if via:
        d = {}
        for k, v in iterable:
            d[k] = v
    TypedDict(**kwargs) -> new dictionary initialized with the name=value
        pairs in the keyword argument list.
        For example:  TypedDict(one=1, two=2)

    TypedDict is a dict that can constrain the types of keys and values
    through the following class variables (if None, have no effect):

        keytype     type                Type of keys
        valtype     type                Type of values
        keymap      {type: type -> keytype}
                                        Mapping from source key type to
                                        function to coerce key to keytype
        valmap      {type: type -> valtype}
                                        Mapping from source val type to
                                        function to coerce val to valtype
        typemap     {key: type}         Set value types for each key

    The set of valid keys may be further constrained:
        valid_keys      [key]           Permit only listed keys
        ignore_invalid  bool            Drop invalid keys silently

    If typemap is defined and valid_keys is not, valid_keys is set to
    typemap.keys(). ignore_invalid permits invalid keys to be silently
    dropped, rather than raising a KeyError.

    The values of keys and values may be constrained with the following
    class methods:
        keyconst    keytype -> bool     Constraint for valid keys
        valconst    valtype -> bool     Constraint for valid values

    A subclass typically only needs to define a couple class variables to
    be useful.
    """
    keytype = valtype = keymap = valmap = valid_keys = typemap = None
    keyconst = valconst = staticmethod(lambda arg: True)
    ignore_invalid = False

    def __init__(self, *args, **kwargs):
        if self.typemap is not None and self.valid_keys is None:
            self.valid_keys = set(self.typemap)

        super(TypedDict, self).__init__()
        if len(args) > 1:
            raise TypeError("{}() takes at most 1 argument ({:d} given)"
                            "".format(self.__class__, len(args)))
        if args or kwargs:
            self.update(*args, **kwargs)

    def __setitem__(self, key, val):
        try:
            key = normalize(key, self.keytype, self.keymap)
        except TypeError:
            raise TypeError('Keys must be of type {!r}'.format(self.keytype))
        try:
            val = normalize(val, self.valtype, self.valmap)
        except TypeError:
            raise TypeError('Values must be of type {!r}'.format(self.keytype))

        if self.typemap is not None and key in self.typemap and \
                type(val) is not self.typemap[key]:
            if self.valmap is not None and type(val) in self.valmap:
                val = self.valmap[type(val)](val)
            val = self.typemap[key](val)

        if self.valid_keys is not None and key not in self.valid_keys:
            if self.ignore_invalid:
                return
            raise KeyError('Invalid key: ' + key)

        if not self.keyconst(key):
            raise KeyError('Invalid key: ' + key)
        if not self.valconst(val):
            raise ValueError('Invalid value: ' + val)
        super(TypedDict, self).__setitem__(key, val)

    def update(self, *args, **kwargs):
        nargs = len(args)
        if nargs > 1:
            raise TypeError("update expected at most 1 arguments, got "
                            "{:d}".format(nargs))
        if args:
            arg = args[0]
            if isinstance(arg, collections.Mapping):
                for key in arg:
                    self[key] = arg[key]
            elif isinstance(arg, collections.Iterable):
                for key, val in arg:
                    self[key] = val

        for key in kwargs:
            self[key] = kwargs[key]

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]


class BytesIndexed(TypedDict):
    keytype = bytes
    keymap = {str: str.encode}


class QueryDict(TypedDict):
    """Dictionary to generate a query string (with no preceding ?)

    Keys must be strings, values must be int(-castable), strings or bytes

    Use str(qdict) to produce a query string with cast and quoted values"""
    keytype = str

    def __str__(self):
        parts = []
        for key, val in self.items():
            if not isinstance(val, (str, bytes)):
                val = str(int(val))
            parts.append('{:s}={:s}'.format(key, urllib.parse.quote(val)))
        return '&'.join(parts)


class OrderedSet(set):
    """A set that permits popping a specific element"""
    def pop(self, n=0):
        x = min(self) if n == 0 else max(self) if n == -1 else sorted(self)[n]
        self.remove(x)
        return x


class DictSet(TypedDict, collections.MutableSet):
    """A set that can be bencoded as a dictionary

    This object can be interacted with either as a set or as a dictionary
    for which all values are True.

    {a, b, c} <=> {a: True, b: True, c: True}
    """
    # Values must be True
    valtype = bool
    valconst = bool

    # Ignore dict implementations
    __ge__ = collections.Set.__ge__
    __gt__ = collections.Set.__gt__
    __le__ = collections.Set.__le__
    __lt__ = collections.Set.__lt__
    __eq__ = collections.Set.__eq__

    @classmethod
    def _normalize_seq(cls, seq):
        """Handle interpretation of sequences and mappings as"""
        if isinstance(seq, collections.Mapping):
            return seq
        if isinstance(seq, collections.Iterable):
            vals = list(seq)
            # Empty
            if not vals:
                return vals
            # Sequence of pairs
            if isinstance(vals[0], collections.Sequence) and \
                    not isinstance(vals[0], (str, bytes)) and \
                    len(vals[0]) == 2:
                return vals
            # Treat as set elements
            return ((element, True) for element in vals)
        raise TypeError("'{}' object is not iterable".format(
                        type(seq).__name__))

    def __init__(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError("{}() expected at most 1 arguments, got {:d}"
                            "".format(self.__class__.__name__, len(args)))
        elif args:
            args = (self._normalize_seq(args[0]),)
        super(DictSet, self).__init__(*args, **kwargs)

    def update(self, *seq):
        for subseq in seq:
            super(DictSet, self).update(self._normalize_seq(subseq))
    update.__doc__ = set.update.__doc__

    # Full set API follows
    def add(self, element):
        self[element] = True

    def discard(self, element):
        TypedDict.pop(self, element, None)

    def pop(self):
        try:
            return self.popitem()[0]
        except KeyError:
            raise KeyError('pop from an empty set')

    def difference(self, seq):
        return self - seq

    def difference_update(self, seq):
        self -= seq

    def intersection(self, seq):
        return self & seq

    def intersection_update(self, seq):
        self &= seq

    def issubset(self, seq):
        return all(elem in seq for elem in self)

    def issuperset(self, seq):
        return all(elem in self for elem in seq)

    def symmetric_difference(self, seq):
        return self ^ seq

    def symmetric_difference_update(self, seq):
        self ^= seq

    def union(self, seq):
        return self | seq
