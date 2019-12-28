from compiler.assembler import *
from compiler.typing import *
from typing import *


class Expr:

    def compile(self, asm: Assembler, operand):
        raise NotImplementedError

    def eval(self):
        assert False

    def addrof(self, asm: Assembler):
        assert False

    def resolve_type(self, func):
        """
        :type func: FunctionDeclaration
        """
        raise NotImplementedError

    def is_lvalue(self):
        return False

    def is_pure(self):
        return False


class ExprIntegerLiteral(Expr):

    def __init__(self, pos, val: int):
        self.pos = pos
        self.val = val

    def eval(self):
        return self.val

    def is_pure(self):
        return True

    def resolve_type(self, func):
        return CInteger(16, True)

    def compile(self, asm: Assembler, operand):
        asm.load(operand, str(self.val))


class ExprIdentLiteral(Expr):

    def __init__(self, pos, name: str):
        self.pos = pos
        self.name = name

    def addrof(self, asm: Assembler):
        var = asm.current_function.get_var(self.name)
        if var is not None:
            return var.storage
        else:
            assert False

    def resolve_type(self, func):
        var = func.get_var(self.name)
        if var is not None:
            return var.type
        else:
            assert False

    def is_lvalue(self):
        return True

    def compile(self, asm: Assembler, operand):
        var = asm.current_function.get_var(self.name)
        if var is not None:
            asm.load(operand, var.storage)
        else:
            assert False


class ExprAddrOf(Expr):

    def __init__(self, pos, expr: Expr):
        self.pos = pos
        self.expr = expr

    def compile(self, asm: Assembler, operand):
        assert self.expr.is_lvalue()
        storage = self.expr.addrof(asm)

        if isinstance(storage, StackAddress):
            asm.load(operand, 'SP')
            if storage.offset != 0:
                asm.append(f'ADD {operand}, {storage.offset}')

        else:
            assert False

    def resolve_type(self, func):
        return CPointer(self.expr.resolve_type(func))


class ExprDeref(Expr):

    def __init__(self, pos, expr: Expr):
        self.pos = pos
        self.expr = expr

    def resolve_type(self, func):
        return self.expr.resolve_type(func).type

    def compile(self, asm: Assembler, operand):
        self.expr.compile(asm, operand)
        asm.load(operand, f'[{operand}]')


class ExprBinary(Expr):

    OPS_UNSIGNED = {
        '+': 'ADD',
        '-': 'SUB',
        '*': 'MUL',
        '/': 'DIV',
        '%': 'MOD',
        '&': 'AND',
        '|': 'BOR',
        '^': 'XOR',
        '>>': 'SHR',
        '<<': 'SHL'
    }

    OPS_SIGNED = {
        '+': 'ADD',
        '-': 'SUB',
        '*': 'MLI',
        '/': 'DVI',
        '%': 'MDI',
        '&': 'AND',
        '|': 'BOR',
        '^': 'XOR',
        '>>': 'ASR',
        '<<': 'SHL'
    }

    def __init__(self, pos, left: Expr, op: str, right: Expr):
        self.pos = pos
        self.left = left
        self.right = right
        self.op = op

    def is_pure(self):
        if self.op[-1] == '=':
            return False

        return self.left.is_pure() and self.right.is_pure()

    def eval(self):
        vala = self.left.eval()
        valb = self.right.eval()

        if self.op == ',':
            return valb
        else:
            return eval(f'{vala} {self.op} {valb}')

    def resolve_type(self, func):
        if self.op == ',':
            return self.right.resolve_type(func)
        else:
            left_type = self.left.resolve_type(func)
            right_type = self.left.resolve_type(func)
            if isinstance(left_type, CPointer):
                return left_type
            elif isinstance(right_type, CPointer):
                return right_type
            else:
                return left_type

    def compile(self, asm: Assembler, operand):
        if self.op == ',':
            if not self.is_pure():
                self.left.compile(asm, operand)

            if self.is_pure():
                asm.load(operand, self.right.eval())
            else:
                self.right.compile(asm, operand)

        elif self.op[-1] == '=':
            assert self.left.is_lvalue()

            # Eval the right value
            if self.right.is_pure():
                asm.load(operand, self.right.eval())
            else:
                self.right.compile(asm, operand)

            # If the op is an assignment and something else then eval it
            if len(self.op[:-1]) != 0:
                asm.append(f'{ExprBinary.OPS_UNSIGNED[self.op[:-1]]} {operand}, {self.left.addrof(asm)}')

            # Store it
            asm.load(self.left.addrof(asm), operand)

        else:
            # TODO: support signed operations
            if self.left.is_pure():
                asm.load(operand, self.left.eval())
            else:
                self.left.compile(asm, operand)

            if self.right.is_pure():
                asm.append(f'{ExprBinary.OPS_UNSIGNED[self.op]} {operand}, {self.right.eval()}')
            else:
                temp = asm.allocate_temp()
                self.right.compile(asm, temp)
                asm.append(f'{ExprBinary.OPS_UNSIGNED[self.op]} {operand}, {temp}')
                asm.free_temp(temp)


class ExprCast(Expr):

    def __init__(self, pos, expr: Expr, type: CType):
        self.pos = pos
        self.expr = expr
        self.type = type

    def is_pure(self):
        return self.expr.is_pure()

    def is_lvalue(self):
        return self.expr.is_lvalue()

    def addrof(self, asm: Assembler):
        return self.expr.addrof(asm)

    def compile(self, asm: Assembler, operand):
        self.expr.compile(asm, operand)

    def resolve_type(self, func):
        return self.type


class Stmt:

    def compile(self, asm: Assembler):
        raise NotImplementedError


class StmtBlock(Stmt):

    def __init__(self):
        self.stmts = []  # type: List[Stmt]

    def append(self, stmt: Stmt):
        if stmt is not None:
            self.stmts.append(stmt)

    def compile(self, asm: Assembler):
        for stmt in self.stmts:
            stmt.compile(asm)


class StmtIf(Stmt):

    def __init__(self, cond: Expr, true_stmt: Stmt, false_stmt: Stmt):
        self.cond = cond
        self.true_stmt = true_stmt
        self.false_stmt = false_stmt

    def compile(self, asm: Assembler):
        if self.cond.is_pure():
            val = self.cond.eval()
            to_compile = self.false_stmt
            if val != 0:
                to_compile = self.true_stmt
            if to_compile is not None:
                to_compile.compile(asm)
        else:
            # TODO: we can optimize this by alot more by using the different if instructions
            else_label = asm.temp_label()

            temp = asm.allocate_temp()
            self.cond.compile(asm, temp)
            asm.free_temp(temp)
            asm.append(f'IFE {temp}, {0}')
            asm.append(f'SET PC, {else_label}')

            self.true_stmt.compile(asm)

            if self.false_stmt is not None:
                end_label = asm.temp_label()
                asm.append(f'SET PC, {end_label}')

                asm.label(else_label)
                self.false_stmt.compile(asm)

                asm.label(end_label)

            else:
                asm.label(else_label)


class StmtReturn(Stmt):

    def __init__(self):
        self.expr = None  # type: None or Expr

    def compile(self, asm: Assembler):
        val = None
        if self.expr is not None:
            val = asm.get_ret()
            if self.expr.is_pure():
                asm.load(val, self.expr.eval())
            else:
                self.expr.compile(asm, val)
        asm.exit_function(val)
        asm.free_temp(val)


class StmtExpr(Stmt):

    def __init__(self, expr: Expr):
        self.expr = expr

    def compile(self, asm):
        if not self.expr.is_pure():
            temp = asm.allocate_temp()
            self.expr.compile(asm, temp)
            asm.free_temp(temp)


class VariableDeclaration:

    def __init__(self, name: str, type: CType, expr: Expr):
        self.name = name
        self.type = type
        self.expr = expr
        self.storage = ''


class FunctionDeclaration:

    def __init__(self):
        self.name = None  # type: str
        self.ret_type = None  # type: CType
        self.args = []  # type: List[Tuple[str, CType]]
        self.static = False  # type: bool
        self.stmts = None  # type: StmtBlock
        self.vars = {}  # type: Dict[str, VariableDeclaration]

    def add_arg(self, name: str, typ: CType):
        self.args.append((name, typ))

    def add_var(self, name: str, typ: CType, expr: Expr):
        assert name not in self.vars
        self.vars[name] = VariableDeclaration(name, typ, expr)

    def get_var(self, name: str):
        if name in self.vars:
            return self.vars[name]
        return None

    def compile(self, asm: Assembler):
        if self.stmts is not None:
            asm.enter_function(self)

            for stmt in self.stmts.stmts:
                stmt.compile(asm)

            asm.exit_function()


class CompilationUnit:

    def __init__(self):
        self.symbols = {}  # type: Dict[str, Union[FunctionDeclaration]]

    def add_symbol(self, symbol):

        if isinstance(symbol, FunctionDeclaration):
            assert symbol.name not in self.symbols
            self.symbols[symbol.name] = symbol

        else:
            assert False

    def remove_symbol(self, symbol):
        assert symbol in self.symbols
        del self.symbols[symbol]

    def get_symbol(self, name):
        if name in self.symbols:
            return self.symbols[name]
        return None

    def compile(self):
        asm = Assembler(AssemblerSyntax.NOTCH)
        for symbol in self.symbols:
            self.symbols[symbol].compile(asm)
        return asm.generate()
