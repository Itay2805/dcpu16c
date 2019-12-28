from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void putc(int c);

int* videoram = 0x8000;

void main() {
    putc('H');
    putc('A');
    putc('I');
}

void putc(int c) {
    *videoram = (0xf << 8) | (0x0 << 12) | (c);
    videoram++;
}
""")
    print(parser.parse().compile())
