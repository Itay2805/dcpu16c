from compiler.parser import Parser
from compiler.ir import IRCompiler
import dumper

if __name__ == '__main__':
    parser = Parser("""
int find(int c, char* s) {
    return *s ? *s == c ? 1 : find(c, s + 1) : 0;
}
""")

    ast = parser.parse()

    print('AST:')
    print('------------------------------')
    for func in ast.func_list:
        print(func)
    print('------------------------------')

    ast.optimize()

    print('Optimized AST:')
    print('------------------------------')
    for func in ast.func_list:
        print(func)
    print('------------------------------')

    comp = IRCompiler(ast)
    comp.compile()

    print('IR:')
    print('------------------------------')
    print(str(comp))
    print('------------------------------')

    comp.optimize()
    print('Optimized IR:')
    print('------------------------------')
    print(str(comp))
    print('------------------------------')
