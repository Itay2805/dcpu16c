from enum import Enum, auto


class Reg(Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    X = 'X'
    Y = 'Y'
    Z = 'Z'
    I = 'I'
    J = 'J'
    PC = 'PC'
    SP = 'SP'
    EX = 'EX'

    def __str__(self):
        return self.value


class Offset:

    def __init__(self, a, offset=0):
        self.a = a
        self.offset = offset

    def __str__(self):
        if self.offset < 0:
            return f'{self.a} - {-self.offset}'
        elif self.offset == 0:
            return f'{self.a}'
        else:
            return f'{self.a} + {self.offset}'


class Deref:

    def __init__(self, a):
        self.a = a

    def __str__(self):
        return f'[{self.a}]'


class Push:

    def __str__(self):
        return 'PUSH'


class Pop:

    def __str__(self):
        return 'POP'


class Assembler:

    def __init__(self):
        self._insts = []
        self._lbl_id_gen = 0
        self._pos = 0

    def put_instruction(self, inst):
        if self._pos < len(self._insts):
            self._insts[self._pos] = inst
        else:
            self._insts.append(inst)
        self._pos += 1

    def get_pos(self) -> int:
        return self._pos

    def set_pos(self, pos: int):
        self._pos = pos

    def get_instructions(self):
        ret = []
        for inst in self._insts:
            if not inst.startswith(';;'):
                ret.append(inst)
        return ret

    def make_label(self):
        id = self._lbl_id_gen
        self._lbl_id_gen += 1
        return f'_l{id}'

    def mark_label(self, lbl):
        self.put_instruction(f'{lbl}:')

    def make_and_mark_label(self):
        lbl = self.make_label()
        self.mark_label(lbl)
        return lbl

    def emit_word(self, word):
        if isinstance(word, list):
            word = ', '.join(word)
        self.put_instruction(f'.dw {word}')

    def emit_string(self, str):
        self.put_instruction(f'.ascii z{repr(str)}')

    def emit_set(self, b, a):
        if str(a) == str(b):
            pass
        else:
            self.put_instruction(f'SET {b}, {a}')

    def emit_add(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'ADD {b}, {a}')

    def emit_sub(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'SUB {b}, {a}')

    def emit_mul(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'MUL {b}, {a}')

    def emit_mli(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'MLI {b}, {a}')

    def emit_div(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'DIV {b}, {a}')

    def emit_dvi(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'DVI {b}, {a}')

    def emit_mod(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'MOD {b}, {a}')

    def emit_mdi(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'MDI {b}, {a}')

    def emit_and(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'AND {b}, {a}')

    def emit_bor(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'BOR {b}, {a}')

    def emit_xor(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'XOR {b}, {a}')

    def emit_shr(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'SHR {b}, {a}')

    def emit_asr(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'ASR {b}, {a}')

    def emit_shl(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'SHL {b}, {a}')

    def emit_ifb(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFB {b}, {a}')

    def emit_ifc(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFC {b}, {a}')

    def emit_ife(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFE {b}, {a}')

    def emit_ifn(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFN {b}, {a}')

    def emit_ifg(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFG {b}, {a}')

    def emit_ifa(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFA {b}, {a}')

    def emit_ifl(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFL {b}, {a}')

    def emit_ifu(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'IFU {b}, {a}')

    def emit_adx(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'ADX {b}, {a}')

    def emit_sbx(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'SBX {b}, {a}')

    def emit_sti(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'STI {b}, {a}')

    def emit_std(self, b, a):
        assert b is not None
        assert a is not None
        self.put_instruction(f'STD {b}, {a}')

    def emit_jsr(self, a):
        assert a is not None
        self.put_instruction(f'JSR {a}')

    def emit_int(self, a):
        assert a is not None
        self.put_instruction(f'INT {a}')

    def emit_iag(self, a):
        assert a is not None
        self.put_instruction(f'IAG {a}')

    def emit_ias(self, a):
        self.put_instruction(f'IAS {a}')

    def emit_rfi(self, a):
        self.put_instruction(f'RFI {a}')

    def emit_iaq(self, a):
        self.put_instruction(f'IAQ {a}')

    def emit_hwn(self, a):
        self.put_instruction(f'HWN {a}')

    def emit_hwq(self, a):
        self.put_instruction(f'HWQ {a}')

    def emit_hwi(self, a):
        self.put_instruction(f'HWI {a}')
