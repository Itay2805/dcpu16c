from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
int add(int a, int b) {
    return a + b;
}
""")
    print(parser.parse().compile())
