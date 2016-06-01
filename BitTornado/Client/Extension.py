from BitTornado.Meta.bencode import bencode, bdecode
# Design
#
# Fundamental:
# extension_name, msg_id, handler
#
# ext_table[msg_id] = (extension_name, handler)
# extensions[extension_name] = msg_id
#
# Ours:
#   msg_id = index
#   ext_table = [(extension_name, handler)]
#
#   ext_lookup = {extension_name: msg_id}
#
# Theirs:
#   msg_id = key
#   handlers =   {msg_id: (extension_name, handler)}
#   extensions = {extension_name: msg_id}
#
#   Default:
#   handlers = {0: (handshake, handshake_handler)}
#   extensions = {handshake: 0}


class _SupportedExtensions(object):
    def __init__(self):
        self.table = [Handshake(None)]
        self.lookup = {}

    def register(self, handler):
        """Register a handler (may be used as decorator)"""
        assert isinstance(handler.name, (bytes, str))
        if handler.name in self.lookup:
            # Previously registered, do nothing
            if self.table[self.lookup[handler.name]] == handler:
                return

            # Previously unregistered, restore
            try:
                msg_id = self.table.index(handler, 1)
                self.lookup[handler.name] = msg_id
            except ValueError:
                pass

        # New handler (possibly replacing existing handler)
        self.lookup[handler.name] = len(self.table)
        self.table.append(handler)
        return handler

    def unregister(self, item):
        if isinstance(item, int):
            msg_id = item
            handler = self.table[item]
        elif isinstance(item, ExtensionHandler):
            handler = item
            try:
                msg_id = self.table.index(item, 1)
            except ValueError:
                raise ValueError("Handler not registered!")

EXTENSIONS = _SupportedExtensions()

class ExtensionHandler(object):
    name = None

    def prepare(self):
        raise NotImplementedError

    def receive(self, payload):
        raise NotImplementedError


class Handshake(ExtensionHandler):
    """Handle the BEP 10 handshake, registering mutually supported handshakes
    for a peer.
    """
    def __init__(self, extensions=None):
        self.exts = extensions
        self.payload = {'m': ext_lookup}

    def prepare(self):
        return bencode(self.payload)

    def receive(self, payload):
        if self.exts is None:
            raise ValueError('This Handshake is not associated with a client.')
        message = bdecode(payload)
        to_add = []
        to_remove = []

        for ext_name, msg_id in message['m']:
            if msg_id == 0:
                to_remove.append(ext_name)
            elif ext_name not in ext_table:
                continue
            elif ext_name not in self.exts.extensions:
                to_add.append((ext_name, msg_id))
            elif self.exts.extensions[ext_name] != msg_id:
                to_remove.append(ext_name)
                to_add.append((ext_name, msg_id))

        if len(to_add) + len(to_remove) == 0:
            return

        handlers = self.exts.handlers.copy()
        extensions = self.exts.extensions.copy()

        for ext_name in to_remove:
            old_id = extensions[ext_name]
            assert handlers[old_id].name == ext_name
            del handlers[old_id]
            del extensions[ext_name]

        for ext_name, msg_id in to_add:
            extensions[ext_name] = msg_id
            handlers[msg_id] = ext_table[ext_lookup[ext_name]]


class PeerExtensions(object):
    def __init__(self):
        self.handlers = {0: Handshake(self)}
        self.extensions = {}

    def __getitem__(self, key):
        return self.handlers[key]
