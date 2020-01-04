from typing import *


class CType:

    def __ne__(self, other):
        return not (self == other)

    def is_complete(self):
        raise NotImplementedError

    def sizeof(self):
        raise NotImplementedError


class CInteger(CType):

    def __init__(self, bits: int, signed: bool):
        self.bits = bits
        self.signed = signed

    def __eq__(self, other):
        if isinstance(other, CInteger):
            return self.signed == other.signed and self.bits == other.bits
        return False

    def sizeof(self):
        return self.bits // 16

    def __str__(self):
        if not self.signed:
            if self.bits == 16:
                return 'unsigned int'
            else:
                assert False
        else:
            if self.bits == 16:
                return 'int'
            else:
                assert False

    def is_complete(self):
        return True


class CPointer(CType):

    def __init__(self, typ: CType):
        self.type = typ

    def sizeof(self):
        return 1

    def __eq__(self, other):
        if isinstance(other, CPointer):
            return other.type == self.type
        return False

    def __str__(self):
        # TODO: show the pointer type properly for functions
        return str(self.type) + '*'

    def is_complete(self):
        return True


class CVoid(CType):

    def __init__(self):
        pass

    def __eq__(self, other):
        return isinstance(other, CVoid)

    def sizeof(self):
        assert False

    def __str__(self):
        return 'void'

    def is_complete(self):
        return False


class CFunction(CType):

    def sizeof(self):
        return 1

    def __init__(self):
        self.ret_type = CVoid()  # type: CType
        self.arg_types = []  # type: List[CType]

    def __str__(self):
        args = ', '.join(map(str, self.arg_types))
        return f'{self.ret_type} (*)({args})'

    def is_complete(self):
        return True


class CArray(CType):

    def __init__(self, typ: CType, len: int or None):
        self.type = typ
        self.len = len

    def sizeof(self):
        assert self.is_complete()
        return self.len * self.type.sizeof()

    def is_complete(self):
        return self.len is not None and self.type.is_complete()

    def __str__(self):
        if self.len is None:
            return f'{self.type}[]'
        else:
            return f'{self.type}[{self.len}]'
