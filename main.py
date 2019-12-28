from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

void main() {
    void* a = 213;
    *(int*)a = 456;
}
""")
    print(parser.parse().compile())
