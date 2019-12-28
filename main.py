from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
__regcall int add(int a, int b) {
    return a + b;
}

int main() {
   return add(1, 2); 
}
""")
    print(parser.parse().compile())
