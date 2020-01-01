from typing import *
from compiler.tokenizer import CodePosition
from compiler.typing import *


########################################################################################################################
# Identifier stuff
########################################################################################################################

# TODO: just have a type instead of different thingies

class Identifier:

    def __init__(self, name, index):
        self.name = name
        self.index = index


class FunctionIdentifier(Identifier):

    def __init__(self, name, index):
        super(FunctionIdentifier, self).__init__(name, index)


class ParameterIdentifier(Identifier):

    def __init__(self, name, index):
        super(ParameterIdentifier, self).__init__(name, index)


class VariableIdentifier(Identifier):

    def __init__(self, name, index):
        super(VariableIdentifier, self).__init__(name, index)


########################################################################################################################
# Expressions
########################################################################################################################

class Expr:

    def is_pure(self, parser):
        raise NotImplementedError

    def resolve_type(self, ast) -> CType:
        assert False

    def __ne__(self, other):
        return not (self == other)


class ExprNop(Expr):

    def __init__(self):
        self.pos = None

    def is_pure(self, parser):
        return True

    def __str__(self, ident=''):
        return ''

    def __eq__(self, other):
        return isinstance(other, ExprNop)


class ExprString(Expr):

    def __init__(self, value: str, pos=None):
        self.pos = pos
        self.value = value

    def is_pure(self, parser):
        return True

    def __str__(self, ident=''):
        return repr(self.value)

    def __eq__(self, other):
        if isinstance(other, ExprString):
            return other.value == self.value
        return False


class ExprNumber(Expr):

    def __init__(self, value: int, pos=None):
        self.pos = pos
        self.value = value

    def resolve_type(self, ast):
        return CInteger(16, False)

    def is_pure(self, parser):
        return True

    def __str__(self, ident=''):
        return str(self.value)

    def __eq__(self, other):
        if isinstance(other, ExprNumber):
            return other.value == self.value
        return False


class ExprIdent(Expr):

    def __init__(self, ident: Identifier, pos=None):
        self.pos = pos
        self.ident = ident

    def resolve_type(self, ast):
        if isinstance(self.ident, VariableIdentifier):
            return ast.func.vars[self.ident.index]
        elif isinstance(self.ident, FunctionIdentifier):
            return CPointer(ast.func_list[self.ident.index].type)
        elif isinstance(self.ident, ParameterIdentifier):
            return ast.func.type.arg_types[self.ident.index]
        else:
            assert False

    def is_pure(self, parser):
        return True

    def __str__(self, ident=''):
        return self.ident.name

    def __eq__(self, other):
        if isinstance(other, ExprIdent):
            return other.ident == self.ident
        return False


class ExprBinary(Expr):

    def __init__(self, left: Expr, op: str, right: Expr, pos=None):
        self.pos = pos

        self.left = left
        self.op = op
        self.right = right

    def resolve_type(self, ast):
        if self.op in ['<<', '>>', '+', '-', '*', '/', '%']:
            # just use the type of the left element
            # TODO: whats the proper way of doing this?
            return self.left.resolve_type(ast)
        elif self.op in ['==', '||', '&&']:
            return CInteger(16, False)
        else:
            assert False

    def is_pure(self, parser):
        return self.left.is_pure(parser) and self.right.is_pure(parser)

    def __str__(self, ident=''):
        return ident + f'({self.left} {self.op} {self.right})'


class ExprLoop(Expr):

    def __init__(self, cond: Expr, body: Expr, pos=None):
        self.pos = pos
        self.cond = cond
        self.body = body

    def is_pure(self, parser):
        return False

    def __str__(self, ident=''):
        return ident + f'(loop {self.cond} {self.body})'


class ExprAddrof(Expr):

    def __init__(self, expr: Expr, pos=None):
        self.pos = pos
        self.expr = expr

    def resolve_type(self, ast):
        return CPointer(self.expr.resolve_type(ast))

    def is_pure(self, parser):
        return True

    def __str__(self, ident=''):
        return ident + f'(addrof {self.expr})'


class ExprDeref(Expr):

    def __init__(self, expr: Expr, pos=None):
        self.pos = pos
        self.expr = expr

    def resolve_type(self, ast):
        t = self.expr.resolve_type(ast)
        assert isinstance(t, CPointer)
        return t.type

    def is_pure(self, parser):
        # return True
        return False

    def __str__(self, ident=''):
        return ident + f'(deref {self.expr})'

    def __eq__(self, other):
        if isinstance(other, ExprDeref):
            return self.expr == other.expr
        return False


class ExprCall(Expr):

    def __init__(self, func: Expr, args: List[Expr], pos=None):
        self.pos = pos
        self.func = func
        self.args = args

    def resolve_type(self, ast):
        func = self.func.resolve_type(ast)
        assert isinstance(func, CPointer)
        assert isinstance(func.type, CFunction)
        return func.type.ret_type

    def is_pure(self, parser):
        if isinstance(self.func, ExprIdent) and isinstance(self.func.ident, FunctionIdentifier):
            called_function = parser.func_list[self.func.ident.index]
            return called_function.pure_known and called_function.pure
        return False

    def __str__(self, ident=''):
        s = ident + f'(call {self.func} ('
        args = []
        for arg in self.args:
            args.append(str(arg))
        s += ', '.join(args) + ')'
        return s


class ExprCopy(Expr):

    def __init__(self, source: Expr, destination: Expr, pos=None):
        self.pos = pos
        self.source = source
        self.destination = destination

    def resolve_type(self, ast) -> CType:
        return self.destination.resolve_type(ast)

    def is_pure(self, parser):
        return False

    def __str__(self, ident=''):
        return ident + f'(copy {self.source} {self.destination})'


class ExprComma(Expr):

    def __init__(self, pos=None):
        assert pos is None or isinstance(pos, CodePosition)
        self.pos = pos
        self.exprs = []  # type: List[Expr]

    def add(self, expr):
        # If a comma expression merge into self
        if isinstance(expr, ExprComma):
            for e in expr.exprs:
                self.exprs.append(e)
        else:
            self.exprs.append(expr)

        # Expand the position
        if self.pos is not None and expr.pos is not None:
            self.pos.end_line = expr.pos.end_line
            self.pos.end_column = expr.pos.end_column

        return self

    def resolve_type(self, ast) -> CType:
        return self.exprs[-1].resolve_type(ast)

    def is_pure(self, parser):
        for expr in self.exprs:
            if not expr.is_pure(parser):
                return False
        return True

    def __str__(self, ident=''):
        s = []
        for expr in self.exprs:
            if len(s) == 0:
                s.append(expr.__str__(ident + '('))
            else:
                s.append(expr.__str__(ident))
        return f'\n{ident + " "}'.join(s) + ')'


class ExprReturn(Expr):

    def __init__(self, expr: Expr, pos=None):
        self.pos = pos
        self.expr = expr

    def is_pure(self, parser):
        return False

    def __str__(self, ident=''):
        return ident + f'(return {self.expr})'


########################################################################################################################
# Function
########################################################################################################################

class Function:

    def __init__(self, name: str):
        self.name = name
        self.code = None
        self.num_params = 0
        self.vars = []  # type: List[Expr]

        self.type = CFunction()

        self.pure = False
        self.pure_known = False

    def __str__(self):
        return f'(func {self.name}\n {self.code.__str__(" ")})'


