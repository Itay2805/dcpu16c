from compiler.typing import *
from enum import Enum


class AssemblerSyntax(Enum):
    # Standards Committee Assembly
    SCA = '0xSCA'
    # The most common syntax on the internet
    DASM16 = 'DASM16'


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

        # registers available for temporaries
        self.free_regs = []
        # registers that we used
        self.used_regs = []
        # registers to save on call
        self.save_on_call = []
        # the function entry point
        self.function_entry = 0
        # all the function exit points
        self.function_exits = []
        # the amount of stack we used for temp variables
        self.temp_stack = 0

        # the stack size we used for local variables
        self.stack_size = 0
        # registers used for temporaries
        self.temp_regs = []
        # the function we are currently compiling for
        self.current_function = None
        # Registers that must be saved on entry
        self.calle_saved = []
        # Registers that must be saved on call
        self.caller_saved = []

    def allocate_temp(self):
        """
        Allocate a temp
        """
        assert len(self.free_regs) != 0
        reg = self.free_regs.pop()
        if reg in self.calle_saved and reg not in self.used_regs:
            self.used_regs.append(reg)
        if reg in self.caller_saved:
            self.save_on_call.append(reg)
        return reg

    def get_ret(self):
        """
        Get the return value register
        """
        # TODO: handle if this is not the case
        # assert 'A' in self.free_regs
        if 'A' in self.free_regs:
            self.free_regs.remove('A')
        return 'A'

    def free_temp(self, temp):
        """
        Free a temp
        """
        if isinstance(temp, RegisterOffset):
            if temp.reg not in self.temp_regs:
                return
            temp = temp.reg

        if temp in self.save_on_call:
            self.save_on_call.remove(temp)

        self.free_regs.append(temp)

    def load(self, op1, op2):
        """
        load op2 to op1
        """
        assert op2 is not None
        if op1 is not None and op1 != op2:
            self.append(f'SET {op1}, {op2}')

    # TODO: allow for non-native types (like structs)
    def prepare_call(self, argscount, callconv: CallingConv):
        # store calle saved
        for reg in self.save_on_call:
            self.load('PUSH', reg)

        if callconv == CallingConv.REGISTER_CALL:
            if argscount > 3:
                self.append(f'SUB SP, {argscount - 3}')
        elif callconv == CallingConv.STACK_CALL:
            if argscount > 0:
                self.append(f'SUB SP, {argscount}')
        else:
            assert False

    def get_arg_location(self, index, callconv: CallingConv):
        if callconv == CallingConv.REGISTER_CALL:
            if index == 0:
                return 'A'
            elif index == 1:
                return 'B'
            elif index == 2:
                return 'C'
            else:
                return RegisterOffset('SP', index - 3)
        elif callconv == CallingConv.STACK_CALL:
            return RegisterOffset('SP', index)

    def clean_call(self, argcount, callconv: CallingConv):
        # Clean the pushed arguments
        if callconv == CallingConv.STACK_CALL:
            if argcount > 0:
                self.append(f'SUB SP, {argcount}')
        elif callconv == CallingConv.REGISTER_CALL:
            if argcount > 3:
                self.append(f'SUB SP, {argcount - 3}')
        else:
            assert False

        # restore calle saved
        for reg in reversed(self.save_on_call):
            self.load(reg, 'POP')

    def goto(self, label):
        """
        goto label
        """
        self.append(f'SET PC, {label}')

    def debug(self, msg):
        if self._debug:
            self.append(f'# {msg}')

    def _fixup_last_function(self):
        assert self.current_function is not None

        # pop all the regs in the exit points
        for exit_index in reversed(self.function_exits):
            for reg in reversed(self.used_regs):
                self.code.insert(exit_index, f'\tSET {reg}, POP')
            if self.temp_stack != 0:
                self.code.insert(exit_index, f'\tSUB SP, {self.temp_stack}')

        # push all the regs in the entry point
        for reg in self.used_regs:
            self.code.insert(self.function_entry, f'\tSET PUSH, {reg}')

        # reset the stuff related to function code gen
        self.free_regs = []
        self.used_regs = []
        self.save_on_call = []
        self.function_entry = 0
        self.function_exits = []
        self.temp_stack = 0
        self.stack_size = 0
        self.current_function = None

    def enter_function(self, func):
        if self.current_function is not None:
            self._fixup_last_function()

        self.current_function = func

        self.code.append('')
        self.label(func.name)

        # TODO: support registercall
        self.calle_saved = "XYZIJ"
        self.caller_saved = "ABC"

        # for register call we are not gonna use registers ABC for simplicity
        if func.calling_convention == CallingConv.STACK_CALL:
            self.temp_regs = ['A', 'B', 'C', 'Y', 'Z', 'I', 'J']
        elif func.calling_convention == CallingConv.REGISTER_CALL:
            self.temp_regs = ['Y', 'Z', 'I', 'J']

        # reset the free regs
        self.free_regs = self.temp_regs[::-1]

        # Allocate the variable locations
        for var in func.vars:
            var = func.vars[var]
            size = var.type.sizeof()
            var.storage = RegisterOffset('X', self.stack_size)
            self.stack_size += size

        # need to skip one for the return pointer
        offset = self.stack_size + 1
        passed = 0
        for arg in reversed(func.args):
            if func.calling_convention == CallingConv.STACK_CALL:
                arg.storage = RegisterOffset('X', offset)
                offset += arg.type.sizeof()

            elif func.calling_convention == CallingConv.REGISTER_CALL:
                if passed == 0:
                    arg.storage = 'A'
                    self.save_on_call.append('A')
                elif passed == 1:
                    arg.storage = 'B'
                    self.save_on_call.append('B')
                elif passed == 2:
                    arg.storage = 'C'
                    self.save_on_call.append('C')
                else:
                    arg.storage = RegisterOffset('X', offset)
                    offset += arg.type.sizeof()

            passed += 1

        if self.stack_size != 0:
            self.append(f'SUB SP, {self.stack_size}')

        self.load('X', 'SP')

        # this is where we want to place stuff
        self.function_entry = len(self.code)

        for var in func.vars:
            var = func.vars[var]
            if var.expr is not None:
                var.expr.compile(self, var.storage)

    def exit_function(self, ret_val=None):
        assert self.current_function is not None

        self.function_exits.append(len(self.code))

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
        elif self.syntax == AssemblerSyntax.DASM16:
            self.code.append(f':{name}')
        else:
            assert False

    def append(self, line):
        self.code.append('\t' + line)

    def generate(self):
        if self.current_function is not None:
            self._fixup_last_function()
        return '\n'.join(self.code)
