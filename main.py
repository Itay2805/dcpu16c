from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

void main() {
    int b;
    int a = 123;
    
    --a;
}
""")
    print(parser.parse().compile())
