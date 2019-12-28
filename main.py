from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void main() {
    *(int*)(0x8000) = (0xf << 8) | (0x0 << 12) | ('A'); 
}
""")
    print(parser.parse().compile())
