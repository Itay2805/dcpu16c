from cc.ast import *
from cc.parser import Parser
from .assembler import *


class Translator:
    """
    Will translate the AST into DCPU16 code

    We use the ABI asm specified here:
    https://github.com/0x10cStandardsCommittee/0x10c-Standards/blob/master/ABI/ABI%20draft%202.txt
    """

    def __init__(self, ast):
        self._ast = ast  # type: Parser
        self._asm = Assembler()

        # Function compilation state
        self._regs = [Reg.I, Reg.Z, Reg.Y, Reg.X, Reg.C, Reg.B, Reg.A]
        self._to_restore = []
        self._save_on_call = []
        self._return_pos = []
        self._stack = 0
        self._params = []
        self._vars = []

        # For break and continue
        self._cond_label = []
        self._end_label = []

    def clear(self):
        """
        Clear the compilation state
        """
        self._regs = [Reg.I, Reg.Z, Reg.Y, Reg.X, Reg.C, Reg.B, Reg.A]
        self._to_restore.clear()
        self._save_on_call.clear()
        self._return_pos.clear()
        self._stack = 0
        self._params.clear()
        self._vars.clear()

    def _can_resolve_to_operand_without_deref(self, expr):
        if isinstance(expr, ExprNumber):
            return True

        elif isinstance(expr, ExprComma):
            return self._can_resolve_to_operand_without_deref(expr.exprs[-1])

        elif isinstance(expr, ExprIdent):
            typ = expr.resolve_type(self._ast)
            # These are resolved to a pointer on the stack so we can resolve them to an operand
            if isinstance(typ, CArray) or isinstance(typ, CStruct):
                return True
            elif isinstance(expr.ident, VariableIdentifier) and isinstance(self._get_var(expr.ident.index), Reg):
                # If this is a variable which is inside a register it will not need a deref
                return True
            elif isinstance(expr.ident, ParameterIdentifier) and isinstance(self._get_param(expr.ident.index), Reg):
                # If this is a parameter which is inside a register it will not need a deref
                return True
            else:
                return False

        elif isinstance(expr, ExprBinary):
            if self._can_resolve_to_operand_without_deref(expr.left) and self._can_resolve_to_operand_without_deref(expr.right):
                left = self._translate_expr(expr.left, None)
                right = self._translate_expr(expr.right, None)
                if isinstance(left, Offset) and isinstance(right, int) or \
                        isinstance(right, Offset) and isinstance(left, int):
                    return True
                else:
                    return False

        elif isinstance(expr, ExprCast):
            return self._can_resolve_to_operand_without_deref(expr.expr)

        elif isinstance(expr, ExprAddrof):
            return True

    def _can_resolve_to_operand(self, expr):
        if self._can_resolve_to_operand_without_deref(expr):
            return True

        elif isinstance(expr, ExprBinary):
            if self._can_resolve_to_operand_without_deref(expr.left) and self._can_resolve_to_operand_without_deref(expr.right):
                left = self._translate_expr(expr.left, None)
                right = self._translate_expr(expr.right, None)
                if isinstance(left, Offset) and isinstance(right, int) or \
                        isinstance(right, Offset) and isinstance(left, int) or \
                        isinstance(left, Reg) and isinstance(right, int) and expr.op in '-+' or \
                        isinstance(right, Reg) and isinstance(left, int) and expr.op in '-+':
                    return True
                else:
                    return False

        elif isinstance(expr, ExprCast):
            return self._can_resolve_to_operand(expr.expr)

        elif isinstance(expr, ExprIdent):
            return True

        elif isinstance(expr, ExprComma):
            return self._can_resolve_to_operand(expr.exprs[-1])

        elif isinstance(expr, ExprDeref):
            if self._can_resolve_to_operand_without_deref(expr.expr):
                return True

        return False

    def _get_param(self, i):
        return self._params[i]

    def _get_var(self, i):
        return self._vars[i]

    def _alloc_scratch(self):
        if len(self._regs) == 0:
            # if out of registers allocate a scratch on the stack
            return self._alloca(2)
        else:
            reg = self._regs.pop()
            if reg in [Reg.J, Reg.Z, Reg.Y, Reg.X] and reg not in self._to_restore:
                self._to_restore.append(reg)
            if reg in [Reg.A, Reg.B, Reg.C] and reg not in self._save_on_call:
                self._save_on_call.append(reg)
            return reg

    def _free_scratch(self, reg: Reg):
        if isinstance(reg, Offset):
            # If this is a spilled register then append it
            # to the start of the list, so it will have least
            # priority on allocation
            self._regs.insert(0, reg)
        else:
            # TODO: put A, B and C first to allocation
            self._regs.append(reg)

            # Remove from caller saved registers if in it
            if reg in self._save_on_call:
                self._save_on_call.remove(reg)

    def _set_scratch(self, reg: Reg):
        # force uses are not put in the restore or save on regcall
        # the function is supposed to make sure it will all work
        if reg in self._regs:
            self._regs.remove(reg)

    def _alloca(self, size):
        self._stack += size
        return Offset(Reg.J, -self._stack)

    def get_instructions(self):
        return self._asm.get_instructions()

    def translate(self):
        for func in self._ast.func_list:
            if func.prototype:
                # Declare asm an external symbol
                self._asm.put_instruction(f'.extern {func.name}')
            else:
                self._translate_function(func)

        for var in self._ast.global_vars:
            # TODO: support constant value for global vars
            if var.storage != StorageClass.STATIC:
                # Declare asm a global symbol if not a static variable
                self._asm.put_instruction(f'.global {var.ident.name}')
            self._asm.mark_label(f'{var.ident.name}')
            self._asm.emit_word(0)

    def _translate_function(self, func: Function):
        # TODO: static functions

        # Clear and set the current function
        self.clear()
        self._ast.func = func

        # label
        self._asm.put_instruction('')
        if func.storage_decl != StorageClass.STATIC:
            self._asm.put_instruction(f'.global {func.name}')
        self._asm.mark_label(func.name)

        # Function entry frame
        self._asm.emit_set(Push(), Reg.J)
        self._asm.emit_set(Reg.J, Reg.SP)

        # setup function argument position
        if func.type.callconv == CallConv.STACKCALL:
            # For stack call all regs are passed on the stack
            off = 2
            for param in func.type.param_types:
                sz = param.sizeof()
                self._params.append(Offset(Reg.J, off))
                off += sz

        elif func.type.callconv == CallConv.REGCALL:
            # For regcall the first free parameters are in A, B and C
            # The rest are passed on the stack
            regs = [Reg.C, Reg.B, Reg.A]
            off = 2
            for param in func.type.param_types:
                if len(regs) != 0:
                    r = regs.pop()
                    self._set_scratch(r)
                    self._params.append(r)
                else:
                    sz = param.sizeof()
                    self._params.append(Offset(Reg.J, off))
                    off += sz
        else:
            assert False

        # Set up local vars
        if len(func.vars) != 0:
            for var in func.vars:
                if var.storage == StorageClass.AUTO:
                    loc = self._alloca(var.typ.sizeof())
                elif var.storage == StorageClass.REGISTER:
                    # Can only do this for register sized stuff
                    if (isinstance(var.typ, CInteger) and var.typ.bits == 16) or \
                            isinstance(var.typ, CPointer) or \
                            isinstance(var.typ, CFunction):
                        loc = self._alloc_scratch()
                    else:
                        loc = self._alloca(var.typ.sizeof())
                elif var.storage == StorageClass.STATIC:
                    # TODO: This is just a global variable
                    assert False
                else:
                    assert False
                self._vars.append(loc)

        # Store place for locals
        locals_pos = self._asm.get_pos()
        self._asm.put_instruction(f';; Locals allocation here')

        # space for saving local regs
        # (X, Y, Z, I)
        for i in range(4):
            self._asm.put_instruction(';; For callee saved stuff')

        # Translate function
        self._translate_expr(func.code, None)

        # Push callee saved and allocate stack area
        # also generate the end code that reverts all of that
        self._asm.set_pos(locals_pos)
        if self._stack > 0:
            self._asm.emit_sub(Reg.SP, self._stack)
        for reg in self._to_restore:
            self._asm.emit_set(Push(), reg)

        # Create all the function frame ends
        for pos in self._return_pos:
            self._asm.set_pos(pos)
            for reg in self._to_restore[::-1]:
                self._asm.emit_set(reg, Pop())
            self._asm.emit_set(Reg.SP, Reg.J)
            self._asm.emit_set(Reg.J, Pop())
            self._asm.emit_set(Reg.PC, Pop())

    def _translate_expr(self, expr: Expr, dest):
        if isinstance(expr, ExprNumber):
            if dest is None:
                return expr.value
            else:
                self._asm.emit_set(dest, expr.value)

        elif isinstance(expr, ExprBreak):
            self._asm.emit_set(Reg.PC, self._end_label[-1])

        elif isinstance(expr, ExprContinue):
            self._asm.emit_set(Reg.PC, self._cond_label[-1])

        elif isinstance(expr, ExprLoop):
            assert dest is None

            end_lbl = self._asm.make_label()
            self._end_label.append(end_lbl)

            # The condition
            cond_lbl = self._asm.make_and_mark_label()
            self._cond_label.append(cond_lbl)
            if self._can_resolve_to_operand(expr.cond):
                cond_result = self._translate_expr(expr.cond, None)
            else:
                cond_result = self._alloc_scratch()
                self._translate_expr(expr.cond, cond_result)
            self._asm.emit_ife(cond_result, 0)
            self._asm.emit_set(Reg.PC, end_lbl)

            if not self._can_resolve_to_operand(expr.cond):
                self._free_scratch(cond_result)

            # The body
            self._translate_expr(expr.body, None)
            self._asm.emit_set(Reg.PC, cond_lbl)

            # Mark the end
            self._asm.mark_label(end_lbl)

        elif isinstance(expr, ExprBinary):
            # Setup the type
            typ = expr.resolve_type(self._ast)
            if isinstance(typ, CInteger):
                assert typ.bits == 16, "Only 16bit math is natively supported"
            elif isinstance(typ, CPointer) or isinstance(typ, CArray):
                typ = CInteger(16, False)
            else:
                assert False, f'`{typ}` ({type(typ)})'

            if dest is None:
                # This allows for doing maths on operands at compile time
                left = self._translate_expr(expr.left, None)
                right = self._translate_expr(expr.right, None)
                if isinstance(left, Offset) and isinstance(right, int):
                    return Offset(left.a, eval(f'{left.offset} {expr.op} {right}'))
                elif isinstance(right, Offset) and isinstance(left, int):
                    return Offset(right.a, eval(f'{right.offset} {expr.op} {left}'))
                elif isinstance(left, Reg) and isinstance(right, int):
                    return Offset(left, right if expr.op == '+' else -right)
                elif isinstance(right, Reg) and isinstance(left, int):
                    return Offset(right, left if expr.op == '+' else -left)
                else:
                    assert False, f'`{left}` and `{right}`'

            else:
                # Translate the left side on the result register
                self._translate_expr(expr.left, dest)

                # Translate the right to a temp one
                if self._can_resolve_to_operand(expr.right):
                    reg = self._translate_expr(expr.right, None)
                else:
                    reg = self._alloc_scratch()
                    self._translate_expr(expr.right, reg)

                # Emit the addition, with dest asm the destination
                if expr.op == '+':
                    self._asm.emit_add(dest, reg)
                elif expr.op == '-':
                    self._asm.emit_sub(dest, reg)
                elif expr.op == '*':
                    self._asm.emit_mul(dest, reg)
                elif expr.op == '/':
                    if typ.signed:
                        self._asm.emit_dvi(dest, reg)
                    else:
                        self._asm.emit_div(dest, reg)
                elif expr.op == '%':
                    if typ.signed:
                        self._asm.emit_mdi(dest, reg)
                    else:
                        self._asm.emit_mod(dest, reg)
                elif expr.op == '&':
                    self._asm.emit_and(dest, reg)
                elif expr.op == '|':
                    self._asm.emit_bor(dest, reg)
                elif expr.op == '^':
                    self._asm.emit_xor(dest, reg)
                else:
                    assert False

                # TODO: Handle ||, &&, ==...

                # Free the scratch register
                if not self._can_resolve_to_operand(expr.right):
                    self._free_scratch(reg)

        elif isinstance(expr, ExprComma):
            last = None
            for e in expr.exprs:
                last = self._translate_expr(e, dest)
            return last

        elif isinstance(expr, ExprNop):
            pass

        elif isinstance(expr, ExprIdent):
            # very similar to addrof but auto derefs
            # there are some special cases, like for arrays
            ident = expr.ident
            if isinstance(ident, VariableIdentifier):
                typ = expr.resolve_type(self._ast)
                var = self._get_var(ident.index)
                # The variable
                if dest is None:
                    # Arrays and structs are turned into pointers
                    if isinstance(typ, CArray) or isinstance(typ, CStruct):
                        return var
                    else:
                        if isinstance(var, Reg):
                            # If this is a register then no need for deref
                            return var
                        else:
                            return Deref(var)
                else:
                    if isinstance(typ, CArray) or isinstance(typ, CStruct):
                        self._translate_expr(ExprAddrof(expr), dest)
                    else:
                        if isinstance(var, Reg):
                            # If this is a register then no need for deref
                            self._asm.emit_set(dest, var)
                        else:
                            self._asm.emit_set(dest, Deref(var))

            elif isinstance(ident, ParameterIdentifier):
                if dest is None:
                    # If the parameter is in register return the register instead
                    if isinstance(self._get_param(ident.index), Reg):
                        return self._get_param(ident.index)
                    else:
                        return Deref(self._get_param(ident.index))
                else:
                    if isinstance(self._get_param(ident.index), Reg):
                        self._asm.emit_set(dest, self._get_param(ident.index))
                    else:
                        self._asm.emit_set(dest, Deref(self._get_param(ident.index)))

            elif isinstance(ident, FunctionIdentifier):
                # The function address is just the label to it
                if dest is None:
                    return ident.name
                else:
                    self._asm.emit_set(dest, ident.name)
            else:
                assert False

        elif isinstance(expr, ExprCast):
            # For cast just use the expression
            return self._translate_expr(expr.expr, dest)

        elif isinstance(expr, ExprCopy):
            tofree = None

            if isinstance(expr.destination, ExprDeref):
                if self._can_resolve_to_operand(expr.destination):
                    dest_op = self._translate_expr(expr.destination, None)

                else:
                    # if the destination can be easily converted into an operand
                    # we will first result the expression that is derefed into
                    # a scratch register and then we will deref that
                    dest_op = self._alloc_scratch()
                    tofree = dest_op
                    self._translate_expr(expr.destination.expr, dest_op)
                    dest_op = Deref(dest_op)

            elif isinstance(expr.destination, ExprIdent):
                dest_op = self._translate_expr(expr.destination, None)
            else:
                assert False, f'`{expr.destination}` ({type(expr.destination)})'

            if self._can_resolve_to_operand_without_deref(expr.source):
                self._asm.emit_set(dest_op, self._translate_expr(expr.source, None))
            else:
                self._translate_expr(expr.source, dest_op)

            # Copy the value from the destination to there
            if dest is not None:
                self._asm.emit_set(dest, dest_op)

            if tofree is not None:
                self._free_scratch(tofree)

        elif isinstance(expr, ExprDeref):
            if dest is None:
                assert self._can_resolve_to_operand(expr.expr)
                return Deref(self._translate_expr(expr.expr, None))
            else:
                if self._can_resolve_to_operand(expr.expr):
                    self._asm.emit_set(dest, Deref(self._translate_expr(expr.expr, None)))
                else:
                    self._translate_expr(expr.expr, dest)
                    self._asm.emit_set(dest, Deref(dest))

        elif isinstance(expr, ExprAddrof):
            if isinstance(expr.expr, ExprIdent):
                ident = expr.expr.ident
                r = None
                if isinstance(ident, VariableIdentifier):
                    # The variable
                    r = self._get_var(ident.index)
                elif isinstance(ident, ParameterIdentifier):
                    # TODO: Support address of parameter in a reg call (probably by spilling it)
                    assert not isinstance(self._get_param(ident.index), Reg)
                    r = self._get_param(ident.index)
                else:
                    assert False

                if dest is not None:
                    if isinstance(r, Offset):
                        self._asm.emit_set(dest, r.a)
                        if r.offset == 0:
                            pass
                        elif r.offset > 0:
                            self._asm.emit_add(dest, r.offset)
                        elif r.offset < 0:
                            self._asm.emit_sub(dest, -r.offset)
                    else:
                        assert False, type(r)
                else:
                    return r
            else:
                assert False, f'`{expr}` ({type(expr)})'

        elif isinstance(expr, ExprCall):
            # TODO: Need the callconv to be part of the type
            callconv = expr.func.resolve_type(self._ast).callconv

            # save the values of A, B and C
            # TODO: need to save it if in arguments or variables properly
            for reg in self._save_on_call:
                self._asm.emit_set(Push(), reg)

            if callconv == CallConv.STACKCALL:
                # place the arguments for a stackcall
                # they are pushed in a reversed order
                for arg in expr.args[::-1]:
                    assert arg.resolve_type(self._ast).sizeof() == 1
                    if self._can_resolve_to_operand(arg):
                        self._asm.emit_set(Push(), self._translate_expr(arg, None))
                    else:
                        # We don't want to set the dest to Push since we might use it in
                        # some other places along the way, making the stack corrupt
                        self._translate_expr(arg, dest)
                        self._asm.emit_set(Push(), dest)
            else:
                assert False

            # Translate the function into a call properly
            if self._can_resolve_to_operand(expr.func):
                self._asm.emit_jsr(self._translate_expr(expr.func, None))
            else:
                if callconv == CallConv.STACKCALL or callconv == CallConv.REGCALL and dest not in [Reg.A, Reg.B, Reg.C]:
                    # If we can use the dest safely then use it to resolve our function
                    self._translate_expr(expr.func, dest)
                    self._asm.emit_jsr(dest)

            # return value is in A
            self._asm.emit_set(dest, Reg.A)

            # restore everything
            if callconv == CallConv.STACKCALL:
                self._asm.emit_add(Reg.SP, len(expr.args))
            elif callconv == CallConv.REGCALL:
                if len(expr.args) > 3:
                    # only need to restore if more than 3 arguments
                    self._asm.emit_add(Reg.SP, (len(expr.args) - 3) - 3)

            # restore the values of A, B and C
            # TODO: need to save it if in arguments or variables properly
            for reg in self._save_on_call[::-1]:
                self._asm.emit_set(reg, Pop())

        elif isinstance(expr, ExprReturn):
            assert dest is None, "Can not have a destination for ExprReturn"
            # The return value is always in A
            if self._can_resolve_to_operand(expr.expr):
                # Check if can be resolved to an operand, if so read it directly
                # if already A then the set will be emitted by the assembler
                self._asm.emit_set(Reg.A, self._translate_expr(expr.expr, None))

            elif Reg.A in self._regs:
                # If A is free use it directly
                self._set_scratch(Reg.A)
                self._translate_expr(expr.expr, Reg.A)

            else:
                # otherwise allocate a scratch and then move it to A
                # at the end
                reg = self._alloc_scratch()
                self._translate_expr(expr.expr, reg)
                self._free_scratch(reg)
                self._asm.emit_set(Reg.A, reg)

            # emit the function ending
            self._return_pos.append(self._asm.get_pos())
            for i in range(7):
                self._asm.put_instruction(';; return stub')
