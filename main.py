from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

void main() {
    int* a = 456;
    a[10] = 123;
}
""")
    print(parser.parse().compile())
