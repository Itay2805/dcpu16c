from compiler.parser import Parser
from compiler.ir import IRCompiler
import dumper

if __name__ == '__main__':
    parser = Parser("""
int main(int c) {
    while(c) {
        c -= 1;
    }
}
""")

    ast = parser.parse()

    if ast.got_errors:
        exit(-1)

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
