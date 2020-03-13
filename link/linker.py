from enum import Enum, auto


class BinaryType(Enum):
    #
    # Raw binary
    #
    RAW = auto()


class Linker:

    def __init__(self):
        self._buffer = []
        self._global_relocs = []
        self._local_relocs = []
        self._symbols = {}
        self.got_errors = False

    def append_object(self, object):
        words, global_relocs, local_relocs, symbols = object
        offset = len(self._buffer)

        # Add the data
        for word in words:
            self._buffer.append(word)

        # relocate anything which needs to be relocated
        for reloc in local_relocs:
            self._local_relocs.append(reloc + offset)
            was = self._buffer[offset + reloc]
            self._buffer[offset + reloc] += offset

        # Relocate and add the global relocations
        for reloc in global_relocs:
            name, pos = reloc
            self._global_relocs.append((name, offset + pos))

        # relocate and add symbols
        for name in symbols:
            pos = symbols[name]
            if name in self._symbols:
                self.report_error(f'multiple definitions of symbol `{name}`')
            else:
                self._symbols[name] = pos + offset

    def rebase(self, base):
        assert False

    def link(self, typ: BinaryType, args):
        # set all the global relocations correctly
        for reloc in self._global_relocs:
            name, pos = reloc
            if name not in self._symbols:
                self.report_error(f'undefined symbol `{name}` referenced')
            else:
                self._buffer[pos] = self._symbols[name]

        if typ == BinaryType.RAW:
            if 'base' in args:
                self.rebase(args['base'])

    def get_words(self):
        return self._buffer

    ####################################################################################################################
    # Error reporting
    ####################################################################################################################

    BOLD = '\033[01m'
    RESET = '\033[0m'
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'

    def report(self, typ: str, col: str, msg: str):
        print(f'{Linker.BOLD}link:{Linker.RESET} {col}{Linker.BOLD}{typ}:{Linker.RESET} {msg}')

    def report_error(self, msg: str):
        self.report('error', Linker.RED, msg)
        self.got_errors = True

    def report_warn(self, msg: str):
        self.report('warning', Linker.YELLOW, msg)

    def report_fatal_error(self, msg: str):
        self.report('error', Linker.RED, msg)
        exit(-1)

