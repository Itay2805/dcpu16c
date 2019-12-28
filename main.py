from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

void main() {
    int a = 213;
    int b = 123;
    a * b;
}
""")
    print(parser.parse().compile())
