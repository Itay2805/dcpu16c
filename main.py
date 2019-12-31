from compiler.parser import Parser
from compiler.ir import IRCompiler
import dumper

if __name__ == '__main__':
    parser = Parser("""
int main(int c) {
    return c ? 0 : 1;
}
""")

    print('AST: \n')

    ast = parser.parse()
    ast._do_constant_folding()
    for func in ast.func_list:
        print(func)

    comp = IRCompiler(ast)
    comp.compile()

    print('\nIR: \n')

    print(str(comp))
