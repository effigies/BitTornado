import urllib


class TypedList(list):
    valtype = valmap = valconst = None

    def __init__(self, iterable):
        super(TypedList, self).__init__()
        self.extend(iterable)

    def append(self, val):
        if self.valtype is not None and type(val) is not self.valtype:
            if self.valmap is not None and type(val) in self.valmap:
                val = self.valmap[type(val)](val)
                if not isinstance(val, self.valtype):
                    raise TypeError('Values must be coercible to type '
                                    '{!r}'.format(self.valtype))
            else:
                try:
                    val = self.valtype(val)
                except TypeError:
                    raise TypeError('Values must be of type {!r}'.format(
                                    self.valtype))

        if self.valconst is not None:
            assert self.valconst(val)

        super(TypedList, self).append(val)

    def __setitem__(self, key, val):
        if self.valtype is not None and type(val) is not self.valtype:
            if self.valmap is not None and type(val) in self.valmap:
                val = self.valmap[type(val)](val)
                if not isinstance(val, self.valtype):
                    raise TypeError('Values must be coercible to type '
                                    '{!r}'.format(self.valtype))
            else:
                try:
                    val = self.valtype(val)
                except TypeError:
                    raise TypeError('Values must be of type {!r}'.format(
                                    self.valtype))

        if self.valconst is not None:
            assert self.valconst(val)

        super(TypedList, self).__setitem__(key, val)

    def extend(self, vals):
        for val in vals:
            self.append(val)


class SplitList(TypedList):
    splitchar = None

    def extend(self, vals):
        if isinstance(vals, type(self.splitchar)):
            vals = vals.split(self.splitchar)
        super(SplitList, self).extend(vals)


class TypedDict(dict):
    keytype = valtype = keymap = valmap = valid_keys = typemap = None
    keyconst = valconst = None

    def __init__(self, mapping=None, **kwargs):
        if self.typemap is not None and self.valid_keys is None:
            self.valid_keys = set(self.typemap)

        super(TypedDict, self).__init__()
        if mapping is None:
            mapping = kwargs.items()
        elif isinstance(mapping, dict):
            mapping = mapping.items()

        for k, v in mapping:
            self[k] = v

    def __setitem__(self, key, val):
        if self.keytype is not None and type(key) is not self.keytype:
            if self.keymap is not None and type(key) in self.keymap:
                key = self.keymap[type(key)](key)
            else:
                try:
                    key = self.keytype(key)
                except TypeError:
                    raise TypeError('Keys must be of type {!r}'.format(
                                    self.keytype))
        if self.valtype is not None and type(val) is not self.valtype:
            if self.valmap is not None and type(val) in self.valmap:
                val = self.valmap[type(val)](val)
            else:
                try:
                    val = self.valtype(val)
                except TypeError:
                    raise TypeError('Values must be of type {!r}'.format(
                                    self.valtype))

        if self.typemap is not None and key in self.typemap and \
                type(val) is not self.typemap[key]:
            if self.valmap is not None and type(val) in self.valmap:
                val = self.valmap[type(val)](val)
            val = self.typemap[key](val)

        if self.valid_keys is not None and key not in self.valid_keys:
            raise KeyError('Invalid key: ' + key)

        if self.keyconst is not None:
            assert self.keyconst(key)
        if self.valconst is not None:
            assert self.valconst(val)
        super(TypedDict, self).__setitem__(key, val)

    def update(self, itr=None, **params):
        """Update TypedDict from an iterable/dict and/or from named parameters
        """
        if itr is not None:
            if hasattr(itr, 'keys'):
                itr = itr.items()
            for key, val in itr:
                self[key] = val

        for key, val in params.items():
            self[key] = val

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
