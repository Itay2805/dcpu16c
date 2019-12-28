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


class RegisterOffset:

    def __init__(self, reg, offset):
        self.reg = reg
        self.offset = offset

    def __str__(self):
        if self.offset == 0:
            return f'[{self.reg}]'
        else:
            return f'[{self.reg} + {self.offset}]'


class Assembler:

    def __init__(self, syntax: AssemblerSyntax, debug=False):
        # the output syntax
        self.syntax = syntax
        # the generated code
        self.code = []

        # label id, for temp label generation
        self.lid = 0
        # are we compiling with debug output
        self._debug = debug

        # the stack size we used for local variables
        self.stack_size = 0
        # registers available for temporaries
        self.free_regs = []
        # registers used for temporaries
        self.temp_regs = []
        # the function we are currently compiling for
        self.current_function = None

    def allocate_temp(self):
        """
        Allocate a temp
        """
        assert len(self.free_regs) != 0
        return self.free_regs.pop()

    def get_ret(self):
        """
        Get the return value register
        """
        return 'A'

    def free_temp(self, temp):
        """
        Free a temp
        """
        if isinstance(temp, RegisterOffset):
            if temp.reg not in self.temp_regs:
                return
            temp = temp.reg
        self.free_regs.append(temp)

    def load(self, op1, op2):
        """
        load op2 to op1
        """
        assert op2 is not None
        if op1 is not None and op1 != op2:
            self.append(f'SET {op1}, {op2}')

    def goto(self, label):
        """
        goto label
        """
        self.append(f'SET PC, {label}')

    def debug(self, msg):
        if self._debug:
            self.append(f'# {msg}')

    def enter_function(self, func):
        self.current_function = func

        self.code.append('')
        self.label(func.name)

        # TODO: support registercall
        self.free_regs = ['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J'][::-1]
        self.temp_regs = ['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J'][::-1]

        for var in func.vars:
            var = func.vars[var]
            size = var.type.sizeof()
            var.storage = RegisterOffset('SP', self.stack_size)
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
