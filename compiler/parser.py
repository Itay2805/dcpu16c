from compiler.tokenizer import *
from compiler.typing import *
from compiler.ast import *


class Parser(Tokenizer):

    def __init__(self, code: str, filename: str = "<unknown>"):
        super(Parser, self).__init__(code, filename)
        self.next_token()
        self.unit = CompilationUnit()
        self.current_function = None

        self.lines = code.splitlines()

    def report_error(self, msg: str):
        pos = self.token.pos

        BOLD = '\033[01m'
        RESET = '\033[0m'
        GREEN = '\033[32m'
        RED = '\033[31m'

        if self.current_function is not None:
            print(f'{BOLD}{self.filename}:{RESET} In function `{BOLD}{self.current_function.name}{RESET}`')

        print(f'{BOLD}{self.filename}:{pos.start_line + 1}:{pos.start_column + 1}:{RESET} {RED}{BOLD}error:{RESET} {msg}')
        line = self.lines[pos.start_line]
        line = line[:pos.start_column] + BOLD + line[pos.start_column:pos.end_column] + RESET + line[pos.end_column:]

        # TODO: color the place in the line
        print(line)

        c = ''
        for i in range(pos.start_column):
            if self.lines[pos.start_line][i] == '\t':
                c += '\t'
            else:
                c += ' '

        print(c + BOLD + RED + '^' + '~' * (pos.end_column - pos.start_column - 1) + RESET)
        print()
        exit(-1)

    def _expand_pos(self, pos1: CodePosition, pos2: CodePosition):
        return CodePosition(pos1.start_line, pos2.end_line, pos1.start_column, pos2.end_column)

    def _check_binary_op(self, tok, e1: Expr, e2: Expr):
        t1 = e1.resolve_type(self.current_function)
        t2 = e2.resolve_type(self.current_function)

        op = tok.value
        pos = tok.pos

        PTR_AND_INT_MATRIX = {
            (CInteger, CInteger),
            (CPointer, CInteger),
            (CInteger, CPointer)
        }

        INT_MATRIX = {
            (CInteger, CInteger)
        }

        OP = {
            '+': PTR_AND_INT_MATRIX,
            '-': PTR_AND_INT_MATRIX,
            '*': INT_MATRIX,
            '/': INT_MATRIX,
            '%': INT_MATRIX,
            '|': INT_MATRIX,
            '&': INT_MATRIX,
            '^': INT_MATRIX,
            '>>': INT_MATRIX,
            '<<': INT_MATRIX,
            '>': PTR_AND_INT_MATRIX,
            '<': PTR_AND_INT_MATRIX,
            '>=': PTR_AND_INT_MATRIX,
            '<=': PTR_AND_INT_MATRIX,
            '==': PTR_AND_INT_MATRIX,
            '!=': PTR_AND_INT_MATRIX
        }

        if op[-1] == '=' and op not in ['<=', '>=', '==', '!=']:
            op = op[:-1]

        for el in OP[op]:
            if isinstance(t1, el[0]) and isinstance(t2, el[1]):
                return

        self.token.pos = pos
        self.report_error(f'invalid operands to binary {op} (have `{t1}` and `{t2}`)')

    def _parse_literal(self):
        if self.is_token(IntToken):
            val = self.token.value
            pos = self.token.pos
            self.next_token()
            return ExprIntegerLiteral(pos, val)

        elif self.is_token(IdentToken):
            val = self.token.value
            pos = self.token.pos
            self.next_token()
            if self.current_function.get_var(val) is None and self.unit.get_symbol(val) is None and self.current_function.name != val:
                self.token.pos = pos
                self.report_error(f'`{val}` undeclared')
            return ExprIdentLiteral(pos, val)

        elif self.match_token('('):
            expr = self._parse_expr()
            self.expect_token(')')
            return expr

        else:
            self.report_error(f'expected expression before {self.token}')

    def _parse_postfix(self):
        e = self._parse_literal()

        pos = self.token.pos
        if self.match_token('++'):
            if not e.is_lvalue():
                self.token.pos = pos
                self.report_error('lvalue required as increment operand')
            e = ExprPostfix(self._expand_pos(e.pos, pos), '++', e)

        elif self.match_token('--'):
            if not e.is_lvalue():
                self.token.pos = pos
                self.report_error('lvalue required as decrement operand')
            e = ExprPostfix(self._expand_pos(e.pos, pos), '--', e)

        elif self.match_token('['):
            sub = self._parse_expr()
            temp_pos = self.token.pos
            self.expect_token(']')

            arr_type = e.resolve_type(self.current_function)
            if not isinstance(arr_type, CPointer):
                self.token.pos = pos
                self.report_error('subscripted value is neither array nor pointer nor vector')

            if not isinstance(sub.resolve_type(self.current_function), CInteger):
                self.token.pos = pos
                self.report_error('array subscript is not an integer')

            return ExprDeref(self._expand_pos(e.pos, temp_pos), ExprBinary(None, e, '+', sub))

        elif self.match_token('('):
            args = []
            temp_pos = self.token.pos
            while not self.match_token(')'):
                args.append(self._parse_assignment())
                if not self.is_token(')'):
                    self.expect_token(',')
                temp_pos = self.token.pos

            # TODO: type checking

            return ExprCall(self._expand_pos(e.pos, temp_pos), e, args)

        return e

    def _parse_prefix(self):
        pos = self.token.pos

        # Address-of
        if self.match_token('&'):
            e = self._parse_prefix()
            if not e.is_lvalue():
                self.token.pos = pos
                self.report_error('lvalue required as unary `&` operand')
            return ExprAddrOf(self._expand_pos(pos, e.pos), e)

        elif self.match_token('*'):
            e = self._parse_prefix()
            typ = e.resolve_type(self.current_function)
            pos = self._expand_pos(pos, e.pos)

            if not isinstance(typ, CPointer):
                self.token.pos = pos
                self.report_error(f'invalid type argument of unary `*` (have `{typ}`)')

            if isinstance(typ.type, CVoid):
                self.token.pos = pos
                self.report_error('dereferencing `void *` pointer')

            return ExprDeref(pos, e)

        elif self.match_token('~'):
            e = self._parse_prefix()
            typ = e.resolve_type(self.current_function)
            pos = self._expand_pos(pos, e.pos)
            if not isinstance(typ, CInteger):
                self.token.pos = pos
                self.report_error(f'invalid type argument of unary `~` (have `{typ}`)')
            return ExprUnary(pos, '~', e)

        elif self.match_token('!'):
            e = self._parse_prefix()
            typ = e.resolve_type(self.current_function)
            pos = self._expand_pos(pos, e.pos)
            if not isinstance(typ, CInteger):
                self.token.pos = pos
                self.report_error(f'invalid type argument of unary `!` (have `{typ}`)')
            return ExprUnary(pos, '!', e)

        elif self.match_token('++'):
            e = self._parse_prefix()
            if not e.is_lvalue():
                self.token.pos = pos
                self.report_error('lvalue required as decrement operand')
            return ExprUnary(self._expand_pos(pos, e.pos), '++', e)

        elif self.match_token('--'):
            e = self._parse_prefix()
            if not e.is_lvalue():
                self.token.pos = pos
                self.report_error('lvalue required as increment operand')
            return ExprUnary(self._expand_pos(pos, e.pos), '--', e)

        # Size-of
        elif self.match_keyword('sizeof'):
            xtype = self._parse_expr().resolve_type(self.current_function).sizeof()
            return ExprIntegerLiteral(self._expand_pos(pos, self.token.pos), xtype)

        # Type cast
        self.push()
        if self.match_token('('):
            typ = self._parse_type(False)
            if typ is not None:
                self.discard()
                self.expect_token(')')
                expr = self._parse_prefix()
                # expr_type = expr.resolve_type(self.current_function)
                # TODO: when we add structs we will need to check for none-scalar type
                return ExprCast(self._expand_pos(pos, self.token.pos), expr, typ)
            else:
                self.pop()
        else:
            self.pop()

        return self._parse_postfix()

    def _parse_multiplicative(self):
        e1 = self._parse_prefix()
        while self.is_token('*') or self.is_token('/') or self.is_token('%'):
            op = self.token
            self.next_token()
            e2 = self._parse_prefix()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_additive(self):
        e1 = self._parse_multiplicative()
        while self.is_token('+') or self.is_token('-'):
            op = self.token
            self.next_token()
            e2 = self._parse_multiplicative()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_shift(self):
        e1 = self._parse_additive()
        while self.is_token('>>') or self.is_token('<<'):
            op = self.token
            self.next_token()
            e2 = self._parse_additive()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_relational(self):
        e1 = self._parse_shift()
        while self.is_token('<') or self.is_token('>') or self.is_token('>=') or self.is_token('<='):
            op = self.token
            self.next_token()
            e2 = self._parse_shift()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_equality(self):
        e1 = self._parse_relational()
        while self.is_token('==') or self.is_token('!='):
            op = self.token
            self.next_token()
            e2 = self._parse_relational()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_bitwise_and(self):
        e1 = self._parse_equality()
        while self.is_token('&'):
            op = self.token
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_bitwise_xor(self):
        e1 = self._parse_equality()
        while self.is_token('^'):
            op = self.token
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_bitwise_or(self):
        e1 = self._parse_equality()
        while self.is_token('|'):
            op = self.token
            self.next_token()
            e2 = self._parse_equality()
            self._check_binary_op(op, e1, e2)
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, op.value, e2)
        return e1

    def _parse_logical_and(self):
        return self._parse_bitwise_or()

    def _parse_logical_or(self):
        return self._parse_logical_and()

    def _parse_conditional(self):
        return self._parse_logical_or()

    def _parse_assignment(self):
        e1 = self._parse_conditional()

        if self.is_token('=') or self.is_token('+=') or self.is_token('-=') or self.is_token('*=') or \
                self.is_token('/=') or self.is_token('%=') or self.is_token('>>=') or self.is_token('<<=') or \
                self.is_token('&=') or self.is_token('^=') or self.is_token('|='):
            op = self.token

            t1 = e1.resolve_type(self.current_function)
            if not e1.is_lvalue() or isinstance(t1, FunctionDeclaration):
                self.report_error('lvalue required as left operand of assignment')

            self.next_token()
            e2 = self._parse_assignment()

            # if has an operational assignment, then turn into the operation
            if op.value != '=':
                self._check_binary_op(op, e1, e2)
                e2 = ExprBinary(op.pos, e1, op.value[:-1], e2)

            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, '=', e2)

        return e1

    def _parse_comma(self):
        e1 = self._parse_assignment()
        while self.match_token(','):
            e2 = self._parse_expr()
            e1 = ExprBinary(self._expand_pos(e1.pos, self.token.pos), e1, ',', e2)
        return e1

    def _parse_expr(self):
        return self._parse_comma()

    def _parse_stmt_block(self):
        block = StmtBlock()
        while not self.match_token('}'):
            block.append(self._parse_stmt())
        return block

    def _parse_stmt(self):
        if self.match_keyword('if'):
            self.expect_token('(')
            cond = self._parse_expr()
            self.expect_token(')')
            true_stmt = self._parse_stmt()
            false_stmt = None
            if self.match_keyword('else'):
                false_stmt = self._parse_stmt()
            return StmtIf(cond, true_stmt, false_stmt)

        elif self.match_keyword('for'):
            assert False

        elif self.match_keyword('while'):
            self.expect_token('(')
            cond = self._parse_expr()
            self.expect_token(')')
            stmt = self._parse_stmt()
            return StmtWhile(cond, stmt)

        elif self.match_keyword('do'):
            assert False

        elif self.match_keyword('switch'):
            assert False

        elif self.match_keyword('return'):
            stmt = StmtReturn()
            if not self.is_token(';'):
                stmt.expr = self._parse_expr()
            self.expect_token(';')
            return stmt

        elif self.match_token('{'):
            return self._parse_stmt_block()

        elif self.match_token(';'):
            return None

        else:
            stmt = StmtExpr(self._parse_expr())
            self.expect_token(';')
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
                self.report_error(f'unknown type name `{name}`')
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

    def _parse_func(self, conv: CallingConv, is_static: bool, name: str, ret_type: CType):
        func = FunctionDeclaration()
        func.unit = self.unit
        func.name = name
        func.ret_type = ret_type
        func.calling_convention = conv
        func.static = is_static
        self.current_function = func

        # Get the params
        self.expect_token('(')

        def parse_arg():
            typ = self._parse_type(True)
            name = None
            if not self.is_token(','):
                name, pos = self.expect_ident()
            func.add_arg(name, typ)

        if not self.match_token(')'):
            parse_arg()
            while self.match_token(','):
                parse_arg()
            self.expect_token(')')

        if self.is_token(';'):
            # Just a function prototype
            pass

        else:
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

                    if func.get_var(name) is not None:
                        self.token.pos = pos
                        self.report_error(f'redefinition of `{name}`')
                    else:
                        func.add_var(name, typ, expr)

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
            func.stmts = self._parse_stmt_block()

        return func

    def parse(self):
        self.unit = CompilationUnit()

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
                is_static = False
                conv = CallingConv.STACK_CALL

                # Handle modifiers for global variables and functions
                while True:
                    # Static modifier
                    if self.is_keyword('static'):
                        if is_static:
                            self.report_error('duplicate `static`')

                        self.next_token()
                        is_static = True

                    elif self.match_keyword('__regcall'):
                        conv = CallingConv.REGISTER_CALL

                    elif self.match_keyword('__stackcall'):
                        conv = CallingConv.STACK_CALL

                    # No more modifiers
                    else:
                        break

                typ = self._parse_type(True)

                # Get the name, making sure there is no definition of it already
                self.push()
                name, name_pos = self.expect_ident()

                # Check if a function
                if self.is_token('('):
                    func = self._parse_func(conv, is_static, name, typ)

                    # Defined Function
                    if func.stmts is not None:
                        # Check not declared already with body
                        orig_func = self.unit.get_symbol(name)
                        if orig_func is not None:
                            # Prev is a full function
                            if orig_func.stmts is not None:
                                self.token.pos = name_pos
                                self.report_error(f'redefinition of `{name}`')

                            # prev is a prototype
                            else:
                                # TODO: make sure not different
                                self.unit.remove_symbol(name)

                        self.unit.add_symbol(func)

                    # Defined Prototype
                    else:
                        # only add if not defined already
                        if self.unit.get_symbol(name) is None:
                            self.unit.add_symbol(func)
                        else:
                            # TODO: make sure not different
                            pass

                # Assume global variable instead
                else:
                    def parse_decl():
                        expr = None

                        # Check the name
                        if self.unit.get_symbol(name) is not None:
                            self.token.pos = name_pos
                            self.report_error(f'redefinition of `{name}`')

                        # parse expression if any
                        if self.match_token('='):
                            expr = self._parse_expr()
                            if not expr.is_pure():
                                self.token.pos = expr.pos
                                self.report_error('initializer element is not constant')

                        # add the symbol
                        self.unit.add_symbol(VariableDeclaration(name, typ, expr))

                    # parse all decls
                    parse_decl()
                    while self.match_token(','):
                        name, name_pos = self.expect_ident()
                        parse_decl()

                    self.expect_token(';')

        return self.unit
