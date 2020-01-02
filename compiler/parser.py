from compiler.tokenizer import *
from compiler.typing import *
from compiler.ast import *


class Parser(Tokenizer):

    def __init__(self, code: str, filename: str = "<unknown>"):
        super(Parser, self).__init__(code, filename)
        self.next_token()

        self._scopes = []  # type: List[Dict[str, Identifier]]
        self.func_list = []  # type: List[Function]
        self.func = None  # type: Function
        self._temp_counter = 0

        self.got_errors = False

    ####################################################################################################################
    # AST Level optimizations
    ####################################################################################################################

    def _find_pure_functions(self):
        for f in self.func_list:
            f.pure_known = False
            f.pure = False

        def check_function(f):

            if f.pure_known:
                return False

            unknown_functions = [False]
            side_effects = False

            def check_side_effects(expr, lvalue=False):
                # Iterate all the expressions
                if isinstance(expr, ExprComma):
                    for e in expr.exprs:
                        if check_side_effects(e):
                            return True
                    return False
                elif isinstance(expr, ExprCopy):
                    return check_side_effects(expr.destination, True) or check_side_effects(expr.source)
                elif isinstance(expr, ExprBinary):
                    return check_side_effects(expr.right) or check_side_effects(expr.left)
                elif isinstance(expr, ExprLoop):
                    return check_side_effects(expr.cond) or check_side_effects(expr.body)
                elif isinstance(expr, ExprAddrof):
                    return check_side_effects(expr.expr)

                # if this is an lvalue and we have a deref we assume side effects
                elif isinstance(expr, ExprDeref):
                    if lvalue:
                        return True
                    else:
                        return check_side_effects(expr.expr)

                elif isinstance(expr, ExprCall):
                    if check_side_effects(expr.func):
                        return True

                    for arg in expr.args:
                        if check_side_effects(arg):
                            return True

                    # assume indirect function calls have side effects
                    if not isinstance(expr.func, ExprIdent) or not isinstance(expr.func.ident, FunctionIdentifier):
                        return True
                    func = self.func_list[expr.func.ident.index]

                    # This function has side effects
                    if func.pure_known and not func.pure:
                        return True

                    if not func.pure_known and func.name != f.name:
                        unknown_functions[0] = True

                else:
                    return False

            side_effects = check_side_effects(f.code)

            if side_effects or not unknown_functions[0]:
                f.pure_known = True
                f.pure = not side_effects
                return True

            return False

        # Iterate until no improvements are found
        count = 0

        for f in self.func_list:
            if check_function(f):
                count += 1

        while count != 0:
            count = 0
            for f in self.func_list:
                if check_function(f):
                    count += 1

    def _constant_fold(self, expr, stmt):
        # TODO: on assign expressions we can probably do some kind of fold inside binary operation
        #       so (5 + (a = 5)) can turn into (a = 5, 10)

        if isinstance(expr, ExprComma):
            new_exprs = []
            for i, e in enumerate(expr.exprs):
                e = self._constant_fold(e, False)

                # If we got to a return just don't continue
                if isinstance(e, ExprReturn):
                    new_exprs.append(e)
                    break

                # elif isinstance(e, ExprLoop):
                #
                #     # Break on loops that never exit
                #     # if isinstance(e.cond, ExprNumber) and e.cond.value != 0:
                #     #     new_exprs.append(e.body)
                #     #     break
                #     #
                #     # else:
                #     new_exprs.append(e)

                # Ignore nops
                elif isinstance(e, ExprNop):
                    continue

                # only add if has side effects
                else:
                    # inside statements we only append non-pure nodes
                    if stmt:
                        if not e.is_pure(self):
                            new_exprs.append(e)

                    # Outside of that only add non-pure and the last element
                    else:
                        if not e.is_pure(self) or i == len(expr.exprs) - 1:
                            new_exprs.append(e)

            if len(new_exprs) == 0:
                return ExprNop()

            if len(new_exprs) == 1:
                return new_exprs[0]

            expr.exprs = new_exprs
            return expr

        elif isinstance(expr, ExprReturn):
            expr.expr = self._constant_fold(expr.expr, False)

        elif isinstance(expr, ExprBinary):
            # TODO: support for multiple expressions in the binary expressions, that will allow
            #       for better constant folding

            expr.left = self._constant_fold(expr.left, False)
            expr.right = self._constant_fold(expr.right, False)

            if expr.op == '&&':
                # We know both
                if isinstance(expr.left, ExprNumber) and isinstance(expr.right, ExprNumber):
                    return 1 if expr.left.value != 0 and expr.right.value != 0 else 0

                # If we first have 0 we can just return 0
                if isinstance(expr.left, ExprNumber):
                    if expr.left.value == 0:
                        return ExprNumber(0)
                    else:
                        return expr.right

                # if the second is a 0 we can just replace this with a comma operator
                if isinstance(expr.right, ExprNumber) and expr.left.value == 0:
                    return ExprComma().add(expr.left).add(ExprNumber(0))

            elif expr.op == '||':
                # We know both
                if isinstance(expr.left, ExprNumber) and isinstance(expr.right, ExprNumber):
                    return ExprNumber(1) if expr.left.value != 0 or expr.right.value != 0 else ExprNumber(0)

                # Left is constant
                if isinstance(expr.left, ExprNumber):
                    # if the left is a 0, then we can simply remove it and
                    # return the right expression
                    if expr.left.value == 0:
                        return expr.right

                    # if left is 1, we can ommit the right expression
                    else:
                        return ExprNumber(1)

                # Right is a const
                if isinstance(expr.right, ExprNumber):
                    # If the const is 0 then the left will be the one
                    # who says what will happen
                    if expr.right.value == 0:
                        return expr.left

                    # If the const is a 1, then it will always be 1
                    # and we can always run the left
                    else:
                        return ExprComma().add(expr.left).add(ExprNumber(1))

            else:
                # The numbers are know and we can calculate them
                if isinstance(expr.left, ExprNumber) and isinstance(expr.right, ExprNumber):
                    return ExprNumber(eval(f'{expr.left} {expr.op} {expr.right}'))

        elif isinstance(expr, ExprDeref):
            expr.expr = self._constant_fold(expr.expr, False)
            # deref an addrof
            if isinstance(expr.expr, ExprAddrof):
                return expr.expr.expr

        elif isinstance(expr, ExprAddrof):
            expr.expr = self._constant_fold(expr.expr, False)
            if isinstance(expr.expr, ExprDeref):
                return expr.expr.expr

        elif isinstance(expr, ExprCopy):
            expr.source = self._constant_fold(expr.source, False)
            expr.destination = self._constant_fold(expr.destination, False)
            # assignment equals to itself and has no side effects
            if expr.source == expr.destination and expr.source.is_pure(self):
                return expr.destination

        elif isinstance(expr, ExprLoop):
            expr.cond = self._constant_fold(expr.cond, False)
            expr.body = self._constant_fold(expr.body, True)

            # The loop has a constant 0
            if isinstance(expr.cond, ExprNumber) and expr.cond.value == 0:
                return ExprNop()

        return expr

    def optimize(self):
        last = str(self)

        self._find_pure_functions()
        for f in self.func_list:
            f.code = self._constant_fold(f.code, True)

        while str(self) != last:
            last = str(self)
            self._find_pure_functions()
            for f in self.func_list:
                f.code = self._constant_fold(f.code, True)

    ####################################################################################################################
    # Helpers
    ####################################################################################################################

    def __str__(self):
        s = []
        for f in self.func_list:
            s.append(str(f))
        return '\n'.join(s)

    def _define(self, name: str, ident: Identifier) -> Expr:
        if self._use(name) is not None:
            return None
        self._scopes[-1][name] = ident
        return ExprIdent(ident)

    def _def_var(self, name, typ) -> Expr:
        ret = self._define(name, VariableIdentifier(name, len(self.func.vars)))
        if ret is None:
            return None
        self.func.vars.append(typ)
        return ret

    def _def_param(self, name, typ) -> Expr:
        ret = self._define(name, ParameterIdentifier(name, self.func.num_params))
        if ret is None:
            return None
        self.func.type.arg_types.append(typ)
        self.func.num_params += 1
        return ret

    def _def_fun(self, name) -> Expr:
        ret = self._define(name, FunctionIdentifier(name, len(self.func_list)))
        return ret

    def _temp(self, typ) -> Expr:
        ret = self._def_var(f'$TEMP{self._temp_counter}', typ)
        self._temp_counter += 1
        return ret

    def _use(self, name: str) -> Expr:
        for scope in reversed(self._scopes):
            if name in scope:
                return ExprIdent(scope[name])
        return None

    def _add_function(self, name: str, typ: CType):
        self.func = Function(name)
        self.func.type.ret_type = typ
        self.func.code = ExprComma()
        self.func_list.append(self.func)

    def _push_scope(self):
        self._scopes.append({})

    def _pop_scope(self):
        self._scopes.pop()

    @staticmethod
    def _combine_pos(pos1: CodePosition, pos2: CodePosition):
        if pos2 is None:
            return pos1
        return CodePosition(pos1.start_line, pos2.end_line, pos1.start_column, pos2.end_column)

    def _check_assignment(self, e1: Expr, e2: Expr):
        t1 = e1.resolve_type(self)
        t2 = e2.resolve_type(self)

        if isinstance(t1, CPointer) and isinstance(t2, CInteger):
            self.report_warn('initialization makes pointer from integer without a cast', e2.pos)
            return True
        elif isinstance(t1, CInteger) and isinstance(t2, CPointer):
            self.report_warn('initialization makes integer from pointer without a cast', e2.pos)
            return True
        elif isinstance(t1, CInteger) and isinstance(t2, CInteger):
            return True
        elif isinstance(t1, CPointer) and isinstance(t2, CPointer):
            if t1.type != t2.type:
                self.report_warn('initialization from incompatible pointer type', e2.pos)
            return True
        else:
            assert False

    def _check_binary_op(self, op: str, pos: CodePosition, e1: Expr, e2: Expr):
        t1 = e1.resolve_type(self)
        t2 = e2.resolve_type(self)

        valid = False

        if op in ['+', '-', '==', '||', '&&']:
            valid = (isinstance(t1, CPointer) or isinstance(t1, CInteger)) and \
                   (isinstance(t2, CPointer) or isinstance(t2, CInteger))
        elif op in ['<<', '>>', '*', '/', '%', '&', '|', '^']:
            valid = isinstance(t1, CInteger) and isinstance(t2, CInteger)
        else:
            assert False

        if not valid:
            self.report_error(f'invalid operands to binary {op} (have `{t1}` and `{t2}`)', pos)

    def _is_lvalue(self, e: Expr):
        return isinstance(e, ExprIdent) or isinstance(e, ExprDeref)

    ####################################################################################################################
    # Error reporting
    ####################################################################################################################

    BOLD = '\033[01m'
    RESET = '\033[0m'
    GREEN = '\033[32m'
    RED = '\033[31m'
    YELLOW = '\033[33m'

    def report(self, typ: str, col: str, msg: str, pos=None):
        if pos is None:
            pos = self.token.pos

        if self.func is not None:
            print(f'{Parser.BOLD}{self.filename}:{Parser.RESET} In function `{Parser.BOLD}{self.func.name}{Parser.RESET}`')

        print(f'{Parser.BOLD}{self.filename}:{pos.start_line + 1}:{pos.start_column + 1}:{Parser.RESET} {col}{Parser.BOLD}{typ}:{Parser.RESET} {msg}')

        line = self.lines[pos.start_line]
        line = line[:pos.start_column] + Parser.BOLD + line[pos.start_column:pos.end_column] + Parser.RESET + line[pos.end_column:]
        print(line)

        c = ''
        for i in range(pos.start_column):
            if self.lines[pos.start_line][i] == '\t':
                c += '\t'
            else:
                c += ' '

        print(c + Parser.BOLD + col + '^' + '~' * (pos.end_column - pos.start_column - 1) + Parser.RESET)
        print()

    def report_error(self, msg: str, pos=None):
        self.report('error', Parser.RED, msg, pos)
        self.got_errors = True

    def report_warn(self, msg: str, pos=None):
        self.report('warning', Parser.YELLOW, msg, pos)

    def report_fatal_error(self, msg: str, pos=None):
        self.report('error', Parser.RED, msg, pos)
        exit(-1)

    # TODO: warning

    ####################################################################################################################
    # Expression parsing
    ####################################################################################################################

    def _parse_literal(self):
        if self.is_token(IntToken):
            val = self.token.value
            pos = self.token.pos
            self.next_token()
            return ExprNumber(val, pos)

        elif self.is_token(IdentToken):
            val = self.token.value
            pos = self.token.pos
            self.next_token()
            expr = self._use(val)
            if expr is None:
                self.report_fatal_error(f'`{val}` undeclared', pos)
            expr.pos = pos
            return expr

        elif self.match_token('('):
            expr = self._parse_expr()
            self.expect_token(')')
            return expr

        else:
            self.report_fatal_error(f'expected expression before {self.token}')

    def _parse_postfix(self):
        x = self._parse_literal()

        while True:

            pos = self.token.pos
            if self.is_token('++') or self.is_token('--'):
                op = self.token.value[0]
                self.next_token()

                if not self._is_lvalue(x):
                    s = 'increment' if op == '+' else 'decrement'
                    self.report_error(f'lvalue required as {s} operand', pos)

                self._check_binary_op(op, pos, x, ExprNumber(1))

                temp = self._temp(x.resolve_type(self))
                if x.is_pure(self):
                    x = ExprComma(self._combine_pos(x.pos, pos))\
                        .add(ExprCopy(x, temp))\
                        .add(ExprCopy(ExprBinary(x, op, ExprNumber(1)), x))\
                        .add(temp)
                else:
                    temp2 = self._temp(x.resolve_type(self))
                    x = ExprComma(self._combine_pos(x.pos, pos))\
                        .add(ExprCopy(ExprAddrof(x), temp))\
                        .add(ExprCopy(ExprDeref(temp), temp2))\
                        .add(ExprCopy(ExprBinary(ExprDeref(temp), op, ExprNumber(1)), ExprDeref(temp)))\
                        .add(temp2)

            elif self.match_token('['):
                sub = self._parse_expr()
                temp_pos = self.token.pos
                self.expect_token(']')

                arr_type = x.resolve_type(self)
                if not isinstance(arr_type, CPointer):
                    self.report_fatal_error('subscripted value is neither array nor pointer', pos)

                if not isinstance(sub.resolve_type(self), CInteger):
                    self.report_error('array subscript is not an integer', pos)

                return ExprDeref(ExprBinary(x, '+', sub), self._combine_pos(x.pos, temp_pos))

            elif self.match_token('('):
                args = []
                temp_pos = self.token.pos
                while not self.match_token(')'):
                    args.append(self._parse_assignment())
                    if not self.is_token(')'):
                        self.expect_token(',')
                    temp_pos = self.token.pos

                return ExprCall(x, args, self._combine_pos(x.pos, temp_pos))

            else:
                break

        return x

    def _parse_prefix(self):
        pos = self.token.pos

        # Address-of
        if self.match_token('&'):
            e = self._parse_prefix()
            if not self._is_lvalue(e):
                self.token.pos = pos
                self.report_error('lvalue required as unary `&` operand')
            return ExprAddrof(e, self._combine_pos(pos, e.pos))

        elif self.match_token('*'):
            e = self._parse_prefix()
            typ = e.resolve_type(self)
            pos = self._combine_pos(pos, e.pos)

            if not isinstance(typ, CPointer):
                self.report_error(f'invalid type argument of unary `*` (have `{typ}`)', pos)

            if isinstance(typ.type, CVoid):
                self.report_error('dereferencing `void *` pointer', pos)

            # Deref of function ptr returns a function ptr
            if isinstance(typ.type, CFunction):
                return e
            else:
                return ExprDeref(e, self._combine_pos(pos, e.pos))

        elif self.match_token('~'):
            e = self._parse_prefix()
            typ = e.resolve_type(self)
            pos = self._combine_pos(pos, e.pos)
            if not isinstance(typ, CInteger):
                self.report_error(f'invalid type argument of unary `~` (have `{typ}`)', pos)
            return ExprBinary(e, '^', ExprNumber(0xFFFF))

        elif self.match_token('!'):
            e = self._parse_prefix()
            typ = e.resolve_type(self)
            pos = self._combine_pos(pos, e.pos)
            if not isinstance(typ, CInteger):
                self.report_error(f'invalid type argument of unary `!` (have `{typ}`)', pos)
            return ExprBinary(e, '==', ExprNumber(0), self._combine_pos(pos, e.pos))

        elif self.is_token('++') or self.is_token('--'):
            op = self.token.value[0]
            self.next_token()
            e = self._parse_prefix()

            if not self._is_lvalue(e):
                s = 'decrement' if op == '-' else 'increment'
                self.report_error(f'lvalue required as {s} operand', pos)

            if e.is_pure(self):
                return ExprCopy(ExprBinary(e, op, ExprNumber(1)), e)
            else:
                temp = self._temp(e.resolve_type(self))
                return ExprComma()\
                    .add(ExprCopy(ExprAddrof(e), temp))\
                    .add(ExprCopy(ExprBinary(ExprDeref(temp), op, ExprNumber(1)), ExprDeref(temp)))

        # Size-of
        elif self.match_keyword('sizeof'):
            xtype = self._parse_expr().resolve_type(self).sizeof()
            return ExprNumber(xtype, self._combine_pos(pos, self.token.pos))

        # Type cast
        # self.push()
        # if self.match_token('('):
        #     typ = self._parse_type(False)
        #     if typ is not None:
        #         self.discard()
        #         self.expect_token(')')
        #         expr = self._parse_prefix()
        #         # expr_type = expr.resolve_type(self.current_function)
        #         # TODO: when we add structs we will need to check for none-scalar type
        #         return ExprCast(self._expand_pos(pos, self.token.pos), expr, typ)
        #     else:
        #         self.pop()
        # else:
        #     self.pop()

        return self._parse_postfix()

    def _parse_multiplicative(self):
        e1 = self._parse_prefix()
        while self.is_token('*') or self.is_token('/') or self.is_token('%'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_prefix()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_additive(self):
        e1 = self._parse_multiplicative()
        while self.is_token('+') or self.is_token('-'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_multiplicative()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_shift(self):
        e1 = self._parse_additive()
        while self.is_token('>>') or self.is_token('<<'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_additive()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op.value, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_relational(self):
        # e1 = self._parse_shift()
        # while self.is_token('<') or self.is_token('>') or self.is_token('>=') or self.is_token('<='):
        #     op = self.token
        #     self.next_token()
        #     e2 = self._parse_shift()
        #     self._check_binary_op(op, e1, e2)
        #     e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        # return e1
        return self._parse_shift()

    def _parse_equality(self):
        e1 = self._parse_relational()
        while self.is_token('==') or self.is_token('!='):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_relational()
            self._check_binary_op(op, pos, e1, e2)
            if op == '==':
                e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
            else:
                e1 = ExprBinary(ExprBinary(e1, '==', e2), '==', ExprNumber(0), self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_bitwise_and(self):
        e1 = self._parse_equality()
        while self.is_token('&'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_bitwise_xor(self):
        e1 = self._parse_equality()
        while self.is_token('^'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op.value, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_bitwise_or(self):
        e1 = self._parse_equality()
        while self.is_token('|'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_logical_and(self):
        e1 = self._parse_bitwise_or()
        while self.is_token('&&'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_bitwise_or()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_logical_or(self):
        e1 = self._parse_logical_and()
        while self.is_token('||'):
            pos = self.token.pos
            op = self.token.value
            self.next_token()
            e2 = self._parse_logical_and()
            self._check_binary_op(op, pos, e1, e2)
            e1 = ExprBinary(e1, op, e2, self._combine_pos(e1.pos, e2.pos))
        return e1

    def _parse_conditional(self):
        x = self._parse_logical_or()

        if self.match_token('?'):
            y = self._parse_conditional()
            pos = self.token.pos
            self.expect_token(':')
            z = self._parse_conditional()

            yt = y.resolve_type(self)
            zt = z.resolve_type(self)
            if yt != zt:
                self.report_error('type mismatch in conditional expression', pos)

            # TODO: this could be awkward if the types mismatch in size
            temp = self._temp(zt)
            x = ExprComma(self._combine_pos(x.pos, z.pos))\
                .add(ExprBinary(ExprBinary(x, '&&', ExprComma().add(ExprCopy(y, temp)).add(ExprNumber(1))), '||', ExprCopy(z, temp)))\
                .add(temp)

        return x

    def _parse_assignment(self):
        x = self._parse_conditional()

        if self.is_token('=') or self.is_token('+=') or self.is_token('-=') or self.is_token('*=') or \
                self.is_token('/=') or self.is_token('%=') or self.is_token('>>=') or self.is_token('<<=') or \
                self.is_token('&=') or self.is_token('^=') or self.is_token('|='):
            op = self.token.value
            pos = self.token.pos

            if not self._is_lvalue(x):
                self.report_error('lvalue required as left operand of assignment', pos)

            self.next_token()
            y = self._parse_assignment()

            self._check_assignment(x, y)

            if op == '=':
                x = ExprCopy(y, x, self._combine_pos(x.pos, y.pos))
            else:
                op = op[:-1]
                if x.is_pure(self):
                    return ExprCopy(ExprBinary(x, op, y), x, self._combine_pos(x.pos, y.pos))
                else:
                    temp = self._temp(CPointer(x.resolve_type(self)))
                    return ExprComma(self._combine_pos(x.pos, y.pos)).add(ExprCopy(ExprAddrof(x), temp)).add(ExprCopy(ExprBinary(ExprDeref(temp), op, y), ExprDeref(temp)))

        return x

    def _parse_comma(self):
        e1 = self._parse_assignment()

        # Turn into a comma if has stuff
        if self.is_token(','):
            e1 = ExprComma().add(e1)

        while self.match_token(','):
            e1.add(self._parse_comma())

        return e1

    def _parse_expr(self):
        return self._parse_comma()

    ####################################################################################################################
    # Statement parsing
    ####################################################################################################################

    def _parse_stmt_block(self):
        block = ExprComma()
        while not self.match_token('}'):
            block.add(self._parse_stmt())
        return block

    def _parse_stmt(self):
        pos = self.token.pos

        if self.match_keyword('if'):
            self.expect_token('(')
            x = self._parse_expr()
            self.expect_token(')')
            y = self._parse_stmt()

            if self.match_keyword('else'):
                z = self._parse_stmt()
                return ExprComma(self._combine_pos(x.pos, z.pos))\
                    .add(ExprBinary(ExprBinary(x, '&&', ExprComma().add(y).add(ExprNumber(1))), '||', z))
            else:
                return ExprBinary(x, "&&", y)

        elif self.match_keyword('for'):
            assert False

        elif self.match_keyword('while'):
            self.expect_token('(')
            cond = self._parse_expr()
            self.expect_token(')')
            body = self._parse_stmt()
            return ExprLoop(cond, body, self._combine_pos(pos, body.pos))

        elif self.match_keyword('do'):
            body = self._parse_stmt()
            self.expect_keyword('while')
            self.expect_token('(')
            cond = self._parse_expr()
            temp_pos = self.token.pos
            self.expect_token(')')
            return ExprComma(self._combine_pos(pos, temp_pos)).add(body).add(ExprLoop(cond, body))

        elif self.match_keyword('switch'):
            assert False

        elif self.match_keyword('return'):
            stmt = ExprReturn(ExprNop())

            if not self.is_token(';'):
                x = self._parse_expr()
                if isinstance(self.func.type.ret_type, CVoid):
                    self.report_warn('`return` with a value, in function returning void', pos)
                    stmt.expr = ExprNop()
                else:
                    stmt.expr = x
            else:
                if not isinstance(self.func.type.ret_type, CVoid):
                    self.report_warn('`return` with no value, in function returning non-void', pos)
                    stmt.expr = ExprNumber(0)

            temp_pos = self.token.pos
            self.expect_token(';')
            stmt.pos = self._combine_pos(pos, temp_pos)
            return stmt

        elif self.match_token('{'):
            return self._parse_stmt_block()

        elif self.match_token(';'):
            return ExprNop()

        else:
            stmt = self._parse_expr()
            temp_pos = self.token.pos
            self.expect_token(';')
            stmt.pos = self._combine_pos(stmt.pos, temp_pos)
            return stmt

    def _parse_type(self, raise_error):
        typ = None
        if self.match_keyword('unsigned'):
            if self.is_keyword('int') or self.is_keyword('char') or self.is_keyword('short'):
                self.next_token()
            typ = CInteger(16, False)

        elif self.match_keyword('signed'):
            if self.is_keyword('int') or self.is_keyword('char') or self.is_keyword('short'):
                self.next_token()
            typ = CInteger(16, True)

        elif self.match_keyword('int') or self.match_keyword('short'):
            typ = CInteger(16, True)

        elif self.match_keyword('char'):
            typ = CInteger(16, False)

        elif self.match_keyword('struct'):
            name, pos = self.expect_ident()
            assert False

        elif self.match_keyword('enum'):
            name, pos = self.expect_ident()
            assert False

        elif self.match_keyword('union'):
            name, pos = self.expect_ident()
            assert False

        elif self.match_keyword('void'):
            typ = CVoid()

        elif self.is_token(IdentToken):
            name, pos = self.expect_ident()
            # TODO: check inside the known types
            if raise_error:
                self.token.pos = pos
                self.report_fatal_error(f'unknown type name `{name}`')
            else:
                return None
        else:
            if raise_error:
                self.expect_ident()
            else:
                return None

        while self.match_token('*'):
            typ = CPointer(typ)

        return typ

    def _parse_func(self):
        # Get the params
        self.expect_token('(')

        def parse_arg():
            typ = self._parse_type(True)

            name, pos = self.expect_ident()

            # TODO: check complete
            if isinstance(typ, CVoid):
                self.report_error(f'parameter {self.func.num_params + 1} (`{name}`) has incomplete type', pos)

            if self._def_param(name, typ) is None:
                self.token.pos = pos
                self.report_fatal_error(f'redefinition of `{name}`')

        if not self.match_token(')'):
            parse_arg()
            while self.match_token(','):
                parse_arg()
            self.expect_token(')')

        # Parse the body
        self.expect_token('{')

        # Parse all the variable declarations
        self.push()
        typ = self._parse_type(False)
        while typ is not None:
            self.discard()

            # Helpers to parse a single decl
            def parse_var_decl():
                name, pos = self.expect_ident()
                expr = None
                if self.match_token('='):
                    expr = self._parse_assignment()

                new_var = self._def_var(name, typ)
                if new_var is None:
                    self.token.pos = pos
                    self.report_fatal_error(f'redefinition of `{name}`')

                if expr is not None:
                    self._check_assignment(new_var, expr)
                    self.func.code.add(ExprCopy(expr, new_var, self._combine_pos(pos, expr.pos)))

            # Parse all the decls
            parse_var_decl()
            while not self.match_token(';'):
                self.expect_token(',')
                parse_var_decl()

            # Next
            self.push()
            typ = self._parse_type(False)
        self.pop()

        # Continue and parse the block
        self._push_scope()
        self.func.code.add(self._parse_stmt_block())
        self._pop_scope()

        # Add an implicit `return 0;`
        if isinstance(self.func.type.ret_type, CVoid):
            self.func.code.add(ExprReturn(ExprNop()))
        else:
            self.func.code.add(ExprReturn(ExprNumber(0)))

    def parse(self):
        self._push_scope()
        while not self.is_token(EofToken):

            # Typedef
            if self.match_keyword('typedef'):
                assert False

            # Struct declaration
            elif self.match_keyword('struct'):
                assert False

            # Enum declaration
            elif self.match_keyword('enum'):
                assert False

            # Union declaration
            elif self.match_keyword('union'):
                assert False

            # Ignore random ;
            elif self.match_token(';'):
                pass

            # Either a global or
            else:
                # Reset the state
                # is_static = False
                # conv = CallingConv.STACK_CALL
                #
                # # Handle modifiers for global variables and functions
                # while True:
                #     # Static modifier
                #     if self.is_keyword('static'):
                #         if is_static:
                #             self.report_error('duplicate `static`')
                #
                #         self.next_token()
                #         is_static = True
                #
                #     elif self.match_keyword('__regcall'):
                #         conv = CallingConv.REGISTER_CALL
                #
                #     elif self.match_keyword('__stackcall'):
                #         conv = CallingConv.STACK_CALL
                #
                #     # No more modifiers
                #     else:
                #         break

                typ = self._parse_type(True)

                # Get the name, making sure there is no definition of it already
                self.push()
                name, name_pos = self.expect_ident()

                # Check if a function
                if self.is_token('('):
                    self._def_fun(name)
                    self._add_function(name, typ)
                    self._parse_func()

                # Assume global variable instead
                else:
                    # def parse_decl():
                    #     expr = None
                    #
                    #     # Check the name
                    #     if self.unit.get_symbol(name) is not None:
                    #         self.token.pos = name_pos
                    #         self.report_error(f'redefinition of `{name}`')
                    #
                    #     # parse expression if any
                    #     if self.match_token('='):
                    #         expr = self._parse_expr()
                    #         if not expr.is_pure():
                    #             self.token.pos = expr.pos
                    #             self.report_error('initializer element is not constant')
                    #
                    #     # add the symbol
                    #     self.unit.add_symbol(VariableDeclaration(name, typ, expr))
                    #
                    # # parse all decls
                    # parse_decl()
                    # while self.match_token(','):
                    #     name, name_pos = self.expect_ident()
                    #     parse_decl()
                    #
                    # self.expect_token(';')
                    pass

        self._pop_scope()

        return self
