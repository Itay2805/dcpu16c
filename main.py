from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

int main() {
    int a = 123;
    return *(a);
}
""")
    print(parser.parse().compile())
