from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

void main() {
    int a = 10;
    int b = 0;
    while(a != b) {
        b++;
    }
    
    while(1);
}
""")
    print(parser.parse().compile())
