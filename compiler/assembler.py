from compiler.typing import *
from enum import Enum


class AssemblerSyntax(Enum):
    # Standards Committee Assembly
    SCA = '0xSCA'
    # The most common syntax on the internet
    NOTCH = 'NOTCH'


class CallingConv(Enum):
    # Uses the stack entirely, caller cleans
    STACK_CALL = 'stackcall'

    # Uses ABC and the stack, caller cleans
    REGISTER_CALL = 'registercall'


class StackAddress:

    def __init__(self, offset):
        self.offset = offset

    def __str__(self):
        if self.offset == 0:
            return '[SP]'
        else:
            return f'[SP + {self.offset}]'


class Assembler:

    def __init__(self, syntax: AssemblerSyntax, debug=False):
        self.syntax = syntax
        self.code = []

        self.lid = 0
        self._debug = debug

        self.stack_size = 0
        self.free_regs = []
        self.current_function = None

    def allocate_temp(self):
        assert len(self.free_regs) != 0
        return self.free_regs.pop()

    def get_ret(self):
        self.free_regs.remove('A')
        return 'A'

    def free_temp(self, temp):
        self.free_regs.append(temp)

    def get_local(self, name):
        assert False

    def get_param(self, name):
        assert False

    def load(self, op1, op2):
        if op1 is not None and op2 is not None and op1 != op2:
            self.append(f'SET {op1}, {op2}')

    def goto(self, label):
        self.append(f'SET PC, {label}')

    def debug(self, msg):
        if self._debug:
            self.append(f'# {msg}')

    def enter_function(self, func):
        self.current_function = func

        self.code.append('')
        self.label(func.name)

        # TODO: support registercall
        self.free_regs = ['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J']

        for var in func.vars:
            var = func.vars[var]
            size = var.type.sizeof()
            var.storage = StackAddress(self.stack_size)
            self.stack_size += size

        if self.stack_size != 0:
            self.append(f'SUB SP, {self.stack_size}')

        for var in func.vars:
            var = func.vars[var]
            if var.expr is not None:
                var.expr.compile(self, var.storage)

    def exit_function(self, ret_val=None):
        assert self.current_function is not None

        if self.stack_size != 0:
            self.append(f'ADD SP, {self.stack_size}')

        # TODO: somehow figure when we don't need this implicit return
        if isinstance(self.current_function.ret_type, CVoid):
            self.append('SET PC, POP')
        elif isinstance(self.current_function.ret_type, CInteger):
            if ret_val is None:
                self.append('SET A, 0')
            self.append('SET PC, POP')
        else:
            assert False

    def temp_label(self):
        l = f'_l{self.lid}'
        self.lid += 1
        return l

    def label(self, name):
        if self.syntax == AssemblerSyntax.SCA:
            self.code.append(f'{name}:')
        elif self.syntax == AssemblerSyntax.NOTCH:
            self.code.append(f':{name}')
        else:
            assert False

    def append(self, line):
        self.code.append('\t' + line)

    def generate(self):
        return '\n'.join(self.code)
