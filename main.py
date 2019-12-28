from compiler.parser import Parser
import dumper

if __name__ == '__main__':
    parser = Parser("""
int add(int a, int b) {
    return a + b;
}

int main() {
    return 0, add(1, 2), 2;
}
""")
    ast = parser.parse()
    ast._do_constant_folding()
    for fun in ast.func_list:
        print(fun)
