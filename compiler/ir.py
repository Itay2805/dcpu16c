from compiler.parser import Parser
from compiler.ast import *


class IRInst:

    def __init__(self):
        self.next = None  # type: None or IRInst

    def num_write_regs(self):
        raise NotImplementedError

    def regs(self):
        raise NotImplementedError

    def read_regs(self):
        for i, regnum in enumerate(self.regs()):
            if i >= self.num_write_regs():
                yield i, regnum

    def write_regs(self):
        for i, regnum in enumerate(self.regs()):
            if i < self.num_write_regs():
                yield i, regnum

    def has_side_effects(self):
        return False

    def __hash__(self):
        return id(self)


class IRNop(IRInst):

    def __init__(self):
        super(IRNop, self).__init__()

    def regs(self):
        return []

    def num_write_regs(self):
        return 0

    def __str__(self):
        return 'NOP'


class IRAlloca(IRInst):
    """
    p0 = alloca(value)
    """

    def __init__(self, p0: int, value: int):
        self.p0 = p0
        self.value = value

    def regs(self):
        return [self.p0]

    def num_write_regs(self):
        return 1

    def __str__(self):
        return f'ALLOCA R{self.p0}, {self.value}'

    def has_side_effects(self):
        return False


class IRInit(IRInst):
    """
    p0 = &ident + value
    """

    def __init__(self, p0: int, ident: str, value: int):
        super(IRInit, self).__init__()
        self.p0 = p0
        self.ident = ident
        self.value = value

    def regs(self):
        return [self.p0]

    def num_write_regs(self):
        return 1

    def __str__(self):
        return f'INIT R{self.p0}, \"{self.ident}\", {self.value}'


class IRMath(IRInst):
    """
    p0 = p1 op p2
    """

    def __init__(self, p0: int, p1: int, p2: int, op: str):
        super(IRMath, self).__init__()
        self.p0 = p0
        self.p1 = p1
        self.p2 = p2
        self.op = op

    def regs(self):
        return [self.p0, self.p1, self.p2]

    def num_write_regs(self):
        return 1

    def __str__(self):
        return f'{self.op} R{self.p0}, R{self.p1}, R{self.p2}'


class IRCopy(IRInst):
    """
    p0 = p1
    """

    def __init__(self, p0: int, p1: int):
        super(IRCopy, self).__init__()
        self.p0 = p0
        self.p1 = p1

    def regs(self):
        return [self.p0, self.p1]

    def num_write_regs(self):
        return 1

    def __str__(self):
        return f'COPY R{self.p0}, R{self.p1}'


class IRAddrof(IRInst):
    """
    NOTE: Whatever that will eventually compile the code into
          machine code will need to make sure to put the variable
          on the stack or whatever so an addrof is possible

    p0 = &p1
    """

    def __init__(self, p0: int, p1: int):
        super(IRAddrof, self).__init__()
        self.p0 = p0
        self.p1 = p1

    def regs(self):
        return [self.p0, self.p1]

    def num_write_regs(self):
        return 1

    def __str__(self):
        return f'ADDROF R{self.p0}, R{self.p1}'


class IRRead(IRInst):
    """
    p0 = *p1
    """

    def __init__(self, p0: int, p1: int):
        super(IRRead, self).__init__()
        self.p0 = p0
        self.p1 = p1

    def regs(self):
        return [self.p0, self.p1]

    def num_write_regs(self):
        return 1

    def __str__(self):
        return f'READ R{self.p0}, R{self.p1}'


class IRWrite(IRInst):
    """
    *p0 = p1
    """

    def __init__(self, p0: int, p1: int):
        super(IRWrite, self).__init__()
        self.p0 = p0
        self.p1 = p1

    def regs(self):
        return [self.p0, self.p1]

    def num_write_regs(self):
        return 0

    def has_side_effects(self):
        return True

    def __str__(self):
        return f'WRITE R{self.p0}, R{self.p1}'


class IRIfnz(IRInst):
    """
    if(p0 != 0) JMP branch
    """

    def __init__(self, p0: int, branch: IRInst):
        super(IRIfnz, self).__init__()
        self.p0 = p0
        self.branch = branch

    def regs(self):
        return [self.p0]

    def num_write_regs(self):
        return 0

    def has_side_effects(self):
        return True

    def __str__(self):
        return f'IFNZ R{self.p0}'


class IRFCall(IRInst):
    """
    p0 = CALL(p1, <params>)
    """

    def __init__(self, p0: int, p1: int, params: List[int]):
        super(IRFCall, self).__init__()
        self.p0 = p0
        self.p1 = p1
        self.params = params

    def num_write_regs(self):
        return 1

    def has_side_effects(self):
        return True

    def regs(self):
        return self.params + [self.p0, self.p1]

    def __str__(self):
        s = f'FCALL R{self.p0}, R{self.p1}'
        for param in self.params:
            s += f', R{param}'
        return s


class IRRet(IRInst):
    """
    RETURN p0
    """

    def __init__(self, p0: int):
        super(IRRet, self).__init__()
        self.p0 = p0

    def regs(self):
        if self.p0 is None:
            return []
        return [self.p0]

    def num_write_regs(self):
        return 0

    def has_side_effects(self):
        return True

    def __str__(self):
        if self.p0 is not None:
            return f'RET R{self.p0}'
        else:
            return f'RET'


class IRContext:

    def __init__(self, init_reg: int, ir: IRInst):
        self.reg_counter = init_reg
        self.last_ir = ir  # type: IRInst
        self.var_to_reg = {}  # type: Dict[int, int]

    def make(self):
        r = self.reg_counter
        self.reg_counter += 1
        return r

    def put(self, *args):
        for ir in args:
            assert isinstance(ir, IRInst)
            self.last_ir.next = ir
            self.last_ir = self.last_ir.next


class AccessInfo:

    class Info:

        def __init__(self):
            self.params = []  # type: List[Set[Tuple[str, int] or None or IRInst]]
            self.presence = []  # type: List[Set[Tuple[str, int] or None or IRInst]]

    def __init__(self, ir, follow_copies: bool, include_ifnz_as_writer: bool):
        """
        :type ir: IRCompiler
        """
        self.data = {}  # type: Dict[IRInst, AccessInfo.Info]
        nodes = ir.get_all_nodes()
        max_reg_number = -1

        for node in nodes:
            if len(node.regs()) != 0:
                max_reg_number = max(max(node.regs()) + 1, max_reg_number)

        if max_reg_number == -1:
            return

        for node in nodes:
            info = AccessInfo.Info()

            for i in range(len(node.regs())):
                info.params.append(set())

            for i in range(max_reg_number):
                info.presence.append(set())

            self.data[node] = info

        for name in ir.entry_points:
            inst = ir.entry_points[name]
            num_params = ir.function_parameters[name]

            state = []  # type: List[Set[Tuple[str, int] or None or IRInst]]
            for i in range(max_reg_number):
                state.append(set())

            # Set all initial register sources
            for r in range(max_reg_number):
                if r < num_params:
                    state[r].add((name, r))
                else:
                    state[r].add(None)

            self._trace(inst, state, follow_copies, include_ifnz_as_writer)

    def _trace(self, where: IRInst, state: List[Set[Tuple[str, int] or None or IRInst]], follow_copies: bool, include_ifnz_as_writer: bool):
        mydata = self.data[where]

        changes = False
        for r in range(len(state)):
            for s in state[r]:
                if s not in mydata.presence[r]:
                    mydata.presence[r].add(s)
                    changes = True

        if follow_copies and isinstance(where, IRCopy):
            if not changes:
                return

            state[where.p0] = set(state[where.p1])
        else:
            for i, regnum in where.read_regs():
                for source in state[regnum]:
                    # Add read info
                    if source not in mydata.params[i]:
                        mydata.params[i].add(source)
                        changes = True

                    # Add write info
                    if isinstance(source, IRInst):
                        for wi, wregnum in source.write_regs():
                            if wregnum == regnum and where not in self.data[source].params[wi]:
                                self.data[source].params[wi].add(where)
                                changes = True

            if include_ifnz_as_writer and isinstance(where, IRIfnz):
                state[where.p0] = {where}

        # if there are no changes to the info just return
        if not changes:
            return

        for _, wregnum in where.write_regs():
            state[wregnum] = {where}

        if isinstance(where, IRIfnz) and where.branch is not None:
            if where.next is None:
                self._trace(where.branch, state, follow_copies, include_ifnz_as_writer)
            else:
                # Create a copy of the state for the branch
                new_state = []
                for s in state:
                    new_state.append(set(s))
                self._trace(where.branch, new_state, follow_copies, include_ifnz_as_writer)

        if where.next is not None:
            self._trace(where.next, state, follow_copies, include_ifnz_as_writer)


class IRCompiler:

    def __init__(self, ast: Parser):
        self.ast = ast
        self.function_parameters = {}  # type: Dict[str, int]
        self.entry_points = {}  # type: Dict[str, IRInst]

        self.compilation_map = {
            ExprDeref: self._compile_deref,
            ExprReturn: self._compile_return,
            ExprNumber: self._compile_number,
            ExprNop: self._compile_nop,
            ExprIdent: self._compile_ident,
            ExprBinary: self._compile_binary,
            ExprComma: self._compile_comma,
            ExprCopy: self._compile_copy,
            ExprAddrof: self._compile_addrof,
            ExprCall: self._compile_call,
            ExprLoop: self._compile_loop,
        }

        self.optimizations = [
            self._optimize_delete_nops,
            self._optimize_jump_threading,
        ]

    ####################################################################################################################
    # The different expression complications
    ####################################################################################################################

    # TODO: do I really need the context?

    def _compile_deref(self, expr: ExprDeref, ctx: IRContext):
        res = ctx.make()
        ctx.put(IRRead(res, self._compile_expr(expr.expr, ctx)))
        return res

    def _compile_return(self, expr: ExprReturn, ctx: IRContext):
        res = self._compile_expr(expr.expr, ctx)
        ctx.put(IRRet(res))
        return res

    def _compile_number(self, expr: ExprNumber, ctx: IRContext):
        res = ctx.make()
        ctx.put(IRInit(res, "", expr.value))
        return res

    def _compile_nop(self, expr: ExprNop, ctx: IRContext):
        ctx.put(IRNop())
        return None

    def _compile_ident(self, expr: ExprIdent, ctx: IRContext):
        if isinstance(expr.ident, FunctionIdentifier):
            res = ctx.make()
            ctx.put(IRInit(res, expr.ident.name, 0))
            return res

        elif isinstance(expr.ident, VariableIdentifier):
            if expr.ident.index not in ctx.var_to_reg:
                ctx.var_to_reg[expr.ident.index] = ctx.make()
            return ctx.var_to_reg[expr.ident.index]

        elif isinstance(expr.ident, ParameterIdentifier):
            return expr.ident.index

        else:
            assert False

    def _compile_binary(self, expr: ExprBinary, ctx: IRContext):
        op_to_ir = {
            '+': 'ADD',
            '-': 'SUB',
            '*': 'MUL',
            '/': 'DIV',
            '%': 'MUL',
            '|': 'BOR',
            '&': 'AND',
            '>>': 'SHR',
            '<<': 'SHL',

            '==': 'EQ'
        }

        # These have special handling and semantics
        if expr.op == '&&' or expr.op == '||':
            res = ctx.make()

            b_then = IRInit(res, "", 1)
            b_else = IRInit(res, "", 0)
            end = IRNop()
            b_then.next = b_else.next = end

            # compile the evaluation of the second part
            temp = ctx.last_ir
            ctx.last_ir = second_cond = IRNop()
            var2 = self._compile_expr(expr.right, ctx)
            second_ifnz = IRIfnz(var2, b_then)
            second_ifnz.next = b_else
            ctx.put(second_ifnz)
            ctx.last_ir = temp

            # compile the evaluation of the first part
            # which will jump to the second part on success
            var1 = self._compile_expr(expr.left, ctx)
            if expr.op == '&&':
                first_ifnz = IRIfnz(var1, second_cond)
                first_ifnz.next = b_else
            else:
                first_ifnz = IRIfnz(var1, b_then)
                first_ifnz.next = second_cond

            ctx.put(first_ifnz)

            ctx.last_ir = end

            return res

        # Nomral math nodes
        else:
            assert expr.op in op_to_ir, f'{expr.op} not in op_to_ir'

            p1 = self._compile_expr(expr.left, ctx)
            p2 = self._compile_expr(expr.right, ctx)

            res = ctx.make()
            ctx.put(IRMath(res, p1, p2, op_to_ir[expr.op]))
            return res

    def _compile_comma(self, expr: ExprComma, ctx: IRContext):
        last = None
        for e in expr.exprs:
            last = self._compile_expr(e, ctx)
        return last

    def _compile_copy(self, expr: ExprCopy, ctx: IRContext):
        if isinstance(expr.destination, ExprDeref):
            res = self._compile_expr(expr.source, ctx)
            ctx.put(IRWrite(self._compile_expr(expr.destination.expr, ctx), res))
            return res
        else:
            temp = self._compile_expr(expr.source, ctx)
            res = self._compile_expr(expr.destination, ctx)
            ctx.put(IRCopy(res, temp))
            return res

    def _compile_addrof(self, expr: ExprAddrof, ctx: IRContext):
        if isinstance(expr.expr, ExprIdent):
            ident = expr.expr.ident
            if isinstance(ident, FunctionIdentifier):
                res = ctx.make()
                ctx.put(IRInit(res, ident.name, 0))
                return res

            elif isinstance(ident, VariableIdentifier):
                res = ctx.make()
                if ident.index not in ctx.var_to_reg:
                    ctx.var_to_reg[ident.index] = ctx.make()
                ctx.put(IRAddrof(res, ctx.var_to_reg[ident.index]))
                return res

            elif isinstance(ident, ParameterIdentifier):
                res = ctx.make()
                ctx.put(IRAddrof(res, ident.index))
                return res

        else:
            assert False

    def _compile_call(self, expr: ExprCall, ctx: IRContext):
        args = []
        for a in expr.args:
            args.append(self._compile_expr(a, ctx))
        res = ctx.make()
        ctx.put(IRFCall(res, self._compile_expr(expr.func, ctx), args))
        return res

    def _compile_loop(self, expr: ExprLoop, ctx: IRContext):
        # the start and end of the loop
        start = IRNop()
        body = IRNop()
        end = IRNop()

        # Put the start and the expression for the check
        ctx.put(start)
        cond = self._compile_expr(expr.cond, ctx)

        # Compare it, if none-zero then go to body, otherwise go to end
        # add this right after the condition thingy
        compare = IRIfnz(cond, body)
        compare.next = end
        ctx.put(compare)

        # now we can compile the body, with the start being the body obviously
        ctx.last_ir = body
        self._compile_expr(expr.body, ctx)

        # After the last one jump to start
        ctx.last_ir.next = start

        # make sure it ends with the last ir
        ctx.last_ir = end

        # no return for loops
        return None

    ####################################################################################################################
    # Top level compilation methods
    ####################################################################################################################

    def _compile_expr(self, expr: Expr, ctx: IRContext) -> int:
        assert type(expr) in self.compilation_map
        return self.compilation_map[type(expr)](expr, ctx)

    def _compile_function(self, func: Function):
        self.function_parameters[func.name] = func.num_params

        ctx = IRContext(func.num_params, self.entry_points[func.name])

        # Allocate whatever needed variables
        for i, var in enumerate(func.vars):
            # Stack allocated array
            if isinstance(var, CArray):
                reg = ctx.make()
                ctx.var_to_reg[i] = reg
                ctx.put(IRAlloca(reg, var.sizeof()))

        # Compile the code
        self._compile_expr(func.code, ctx)

    def compile(self):
        for func in self.ast.func_list:
            self.entry_points[func.name] = IRNop()

        for func in self.ast.func_list:
            self._compile_function(func)

    ####################################################################################################################
    # Optimization
    ####################################################################################################################

    def get_access_info(self, follow_copies: bool, include_ifnz_as_writer: bool = False) -> Dict[IRInst, AccessInfo.Info]:
        return AccessInfo(self, follow_copies, include_ifnz_as_writer).data

    def get_all_nodes(self):
        # get all the nodes inside the ir
        all_nodes = set()
        for func in self.entry_points:
            c = self.entry_points[func]

            def iterate_all_nodes(node):
                while node is not None:
                    # if already found this we can be assured
                    # the rest were found as well
                    if node in all_nodes:
                        break

                    # add the node we are looking at
                    all_nodes.add(node)

                    # if found a branch then go to it
                    if isinstance(node, IRIfnz):
                        iterate_all_nodes(node.branch)

                    # go to the next node
                    node = node.next

            iterate_all_nodes(c)

        return all_nodes

    def _reach(self, frm: IRInst, to: IRInst, exclude: IRInst = None):
        visited = set()
        pending = [frm]  # type: List[IRInst]

        while len(pending) != 0:
            chain = pending.pop()

            if chain == exclude or chain in visited:
                continue
            visited.add(chain)

            if chain == to:
                return True

            if isinstance(chain, IRIfnz) and chain.branch is not None:
                pending.append(chain.branch)

            if chain.next is not None:
                pending.append(chain.next)

        return False

    def _optimize_delete_nops(self, nodes):
        changed = False
        info = self.get_access_info(False)

        def reduce_nop_chain(p: IRInst):
            nonlocal changed

            # will return the first element which is not a:
            # - NOP
            # - COPY with both sides being the same
            # - IFNZ with both branches being the same
            # - Any modify instruction where the target is never read after
            #   and has no side effects
            counter = 0
            counter_max = 1
            seen = p
            while p is not None:
                reads_after_write = False
                for i, _ in p.write_regs():
                    if len(info[p].params[i]) != 0:
                        reads_after_write = True
                        break

                if not isinstance(p, IRNop) and \
                        not (isinstance(p, IRIfnz) and (p.next == p.branch or p.branch is None)) and\
                        not (isinstance(p, IRCopy) and p.p0 == p.p1) and\
                        (p.has_side_effects() or reads_after_write):
                    return p

                if p.next == seen:
                    return p

                counter += 1
                if counter == counter_max:
                    seen = p
                    counter = 0
                    counter_max <<= 1

                p = p.next

        # reduce nops from functions entries
        for t in self.entry_points:
            self.entry_points[t] = reduce_nop_chain(self.entry_points[t])

        for s in nodes:
            # remove nops from the next
            s.next = reduce_nop_chain(s.next)

            # Make sure to remove nops from the branch
            if isinstance(s, IRIfnz):
                s.branch = reduce_nop_chain(s.branch)

            # Remove everything after a RET
            elif isinstance(s, IRRet):
                if s.next is not None:
                    changed = True
                    s.next = None

        return changed

    def _optimize_jump_threading(self, nodes):
        changed = False

        def reduce_it(node: IRInst):
            nonlocal changed

            while isinstance(node, IRIfnz) and \
                        node.next is not None and\
                        isinstance(node.next, IRIfnz) and\
                        node.p0 == node.next.p0 and\
                        node.next != node.next.next:
                node.next = node.next.next
                changed = True

            # same with the branch
            while isinstance(node, IRIfnz) and \
                    node.branch is not None and \
                    isinstance(node.branch, IRIfnz) and \
                    node.p0 == node.branch.p0 and \
                    node.branch != node.branch.branch:
                node.branch = node.branch.branch
                changed = True

            # If we have an init and then an ifnz right after it we can know right
            # away if there will be a branch or not
            while isinstance(node, IRInit) and\
                    node.ident == '' and\
                    node.next is not None and\
                    isinstance(node.next, IRIfnz) and\
                    node.p0 == node.next.p0:
                node.next = node.next.branch if node.value else node.next.next
                changed = True

            # TODO: need to figure a way to convert a node completely...
            # if we do a copy and then do a ret with the parameter we copied to
            # then we can just return the parameter we copied from
            while isinstance(node, IRCopy) and\
                    node.next is not None and\
                    isinstance(node.next, IRRet) and\
                    node.p0 == node.next.p0:
                node = IRRet(node.p1)
                changed = True

            return node

        for t in self.entry_points:
            self.entry_points[t] = reduce_it(self.entry_points[t])

        for s in nodes:
            # remove nops from the next
            s.next = reduce_it(s.next)

            # Make sure to remove nops from the branch
            if isinstance(s, IRIfnz):
                s.branch = reduce_it(s.branch)

            # Remove everything after a RET
            elif isinstance(s, IRRet):
                if s.next is not None:
                    changed = True
                    s.next = None

        return changed

    # TODO: tree merging, can make the code alot smaller (won't make it faster tho)
    #       given that the dcpu16 does not have alot of memory it would be a nice
    #       addition to the compiler

    def optimize(self):
        nodes = self.get_all_nodes()
        while nodes is not None:
            changed = False
            for opt in self.optimizations:
                if opt(nodes):
                    changed = True
            nodes = self.get_all_nodes() if changed else None

    ####################################################################################################################
    # Debug
    ####################################################################################################################

    def __str__(self):

        label_count = 0

        class Data:
            def __init__(self):
                self.labels = []  # type: List[str]
                self.done = False
                self.referred = False

            def add_label(self):
                nonlocal label_count
                self.labels.append(f'L{label_count}')
                label_count += 1

        statistics = {}  # type: Dict[IRInst, Data]
        remaining_insts = []  # type: List[IRInst]

        s = ''

        for func in self.entry_points:
            ir = self.entry_points[func]
            remaining_insts.append(ir)
            statistics[ir] = Data()
            statistics[ir].labels.append(func)

        all_nodes = self.get_all_nodes()

        for node in all_nodes:
            # Handle the next element
            if node.next not in statistics:
                statistics[node.next] = Data()
            if len(statistics[node.next].labels) == 0:
                was = statistics[node.next].referred
                statistics[node.next].referred = True
                if was:
                    statistics[node.next].add_label()

            # Handle the branch element
            if isinstance(node, IRIfnz):
                if node.branch not in statistics:
                    statistics[node.branch] = Data()
                if len(statistics[node.branch].labels) == 0:
                    statistics[node.branch].add_label()

        need_jump = False
        while len(remaining_insts) != 0:
            chain = remaining_insts.pop()
            while chain is not None:

                stats = statistics[chain]
                was = stats.done
                stats.done = True
                if was:
                    if need_jump:
                        s += f'\tJMP {stats.labels[0]}\n'
                        break

                for label in stats.labels:
                    s += f'{label}:\n'

                s += '\t' + str(chain)
                if isinstance(chain, IRIfnz):
                    branch_stats = statistics[chain.branch]
                    s += f', JMP {branch_stats.labels[0]}'
                    if not branch_stats.done:
                        remaining_insts.append(chain.branch)

                s += '\n'

                chain = chain.next
                need_jump = True

        return s
