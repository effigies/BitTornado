from types import *

def formatDefinitions(options, COLS, presets = {}):
    spaces = " " * 10
    width = COLS - (11)
    if width < 15:
        width = COLS - 2
        spaces = " "

    lines = []
    for (longname, default, doc) in options:
        lines.append("--{} <arg>".format(longname))
        default = presets.get(longname, default)
        if default:
            doc += ' (defaults to {})'.format(default)

        # Word wrap documentation string
        while len(doc) > width:
            pre, sep, post = doc[:width].rpartition(' ')
            doc = post + doc[width:]
            lines.append(spaces + pre)
        if doc:
            lines.append(spaces + doc)

        lines.append('')
    return '\n'.join(lines)

def usage(str):
    raise ValueError(str)

def defaultargs(options):
    return dict((longname, default) for longname, default, doc in options
                                        if default is not None)

def parseargs(argv, options, minargs = None, maxargs = None, presets = {}):
    config = {}
    longkeyed = {}
    for option in options:
        longname, default, doc = option
        longkeyed[longname] = option
        config[longname] = default

    config.update(presets) # presets after defaults but before arguments

    options = []
    args = []
    pos = 0
    while pos < len(argv):
        if argv[pos][:2] != '--':
            args.append(argv[pos])
            pos += 1
        else:
            if pos == len(argv) - 1:
                usage('parameter passed in at end with no value')
            key, value = argv[pos][2:], argv[pos+1]
            pos += 2
            if key not in longkeyed:
                usage('unknown key --' + key)
            longname, default, doc = longkeyed[key]
            try:
                t = type(config[longname])
                if t is NoneType or t is StringType:
                    config[longname] = value
                elif t in (IntType, LongType):
                    config[longname] = long(value)
                elif t is FloatType:
                    config[longname] = float(value)
                else:
                    assert 0
            except ValueError, e:
                usage('wrong format of --%s - %s' % (key, str(e)))
    for key, value in config.iteritems():
        if value is None:
            usage("Option --%s is required." % key)
    if minargs is not None and len(args) < minargs:
        usage("Must supply at least %d args." % minargs)
    if maxargs is not None and len(args) > maxargs:
        usage("Too many args - %d max." % maxargs)
    return (config, args)

def test_parseargs():
    assert parseargs(('d', '--a', 'pq', 'e', '--b', '3', '--c', '4.5', 'f'), (('a', 'x', ''), ('b', 1, ''), ('c', 2.3, ''))) == ({'a': 'pq', 'b': 3, 'c': 4.5}, ['d', 'e', 'f'])
    assert parseargs([], [('a', 'x', '')]) == ({'a': 'x'}, [])
    assert parseargs(['--a', 'x', '--a', 'y'], [('a', '', '')]) == ({'a': 'y'}, [])
    try:
        parseargs([], [('a', 'x', '')])
    except ValueError:
        pass
    try:
        parseargs(['--a', 'x'], [])
    except ValueError:
        pass
    try:
        parseargs(['--a'], [('a', 'x', '')])
    except ValueError:
        pass
    try:
        parseargs([], [], 1, 2)
    except ValueError:
        pass
    assert parseargs(['x'], [], 1, 2) == ({}, ['x'])
    assert parseargs(['x', 'y'], [], 1, 2) == ({}, ['x', 'y'])
    try:
        parseargs(['x', 'y', 'z'], [], 1, 2)
    except ValueError:
        pass
    try:
        parseargs(['--a', '2.0'], [('a', 3, '')])
    except ValueError:
        pass
    try:
        parseargs(['--a', 'z'], [('a', 2.1, '')])
    except ValueError:
        pass

