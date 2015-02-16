'''
reads/writes a Windows-style INI file
format:

  aa = "bb"
  cc = 11

  [eee]
  ff = "gg"

decodes to:
d = { '': {'aa':'bb','cc':'11'}, 'eee': {'ff':'gg'} }

the encoder can also take this as input:

d = { 'aa': 'bb, 'cc': 11, 'eee': {'ff':'gg'} }

though it will only decode in the above format.  Keywords must be strings.
Values that are strings are written surrounded by quotes, and the decoding
routine automatically strips any.
Booleans are written as integers.  Anything else aside from string/int/float
may have unpredictable results.
'''


def ini_write(fname, data, comment=''):
    config = {'': {}}

    # Bring data dictionary into line with expectations
    for key, value in data.iteritems():
        if isinstance(value, dict):
            config[key.lower()] = value
        else:
            config[''][key.lower()] = value

    lines = []

    if comment:
        lines.extend('# {}'.format(line) for line in comment.split('\n'))
        lines.append('')

    for section in sorted(config):

        # Add section headers, except to ''
        if section:
            lines.append('[{}]'.format(section))

        subconf = config[section]
        for key in sorted(subconf):
            value = subconf[key]

            # Modify string and boolean types
            if isinstance(value, str):
                value = '"{}"'.format(value)
            elif isinstance(value, bool):
                value = int(value)

            lines.append("{} = {}".format(key, value))

        lines.append('')

    try:
        with open(fname, 'w') as ini_file:
            ini_file.write('\n'.join(lines))
        return True
    except IOError:
        return False


def ini_read(fname, errfunc=lambda *x: None):
    subconf = {}
    config = {'': subconf}
    try:
        with open(fname, 'r') as ini_file:
            for num, line in enumerate(ini_file):
                contents = line.strip()
                if not contents or contents[0] == '#':
                    continue
                if contents[0] == '[':
                    if contents[-1] != ']':
                        errfunc(num, line, 'Expected: [x]')
                        continue
                    subconf = config.setdefault(contents[1:-1].strip().lower(),
                                                {})
                    continue

                key, sep, value = map(str.strip, contents.partition("="))
                if not sep:
                    key, sep, value = map(str.strip, contents.partition(":"))
                if not sep:
                    errfunc(num, line, 'Expected: x=y or x:y')
                    continue

                if value[0] in ("'", '"'):
                    if value[-1] != value[0]:
                        errfunc(num, line, 'Quotes must surround entire value')
                        continue
                    value = value[1:-1]

                key = key.lower()
                if key in subconf:
                    errfunc(num, line, 'Duplicate entry')

                subconf[key] = value

    except IOError:
        return {}

    return config
