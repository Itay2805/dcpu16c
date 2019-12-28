from compiler.parser import Parser


if __name__ == '__main__':
    parser = Parser("""
void another_function();

int main() {
    int a = 10;
    int count = 0;
    while(a) {
        a -= 1;
        count += 1;
    }
    return count;
}
""")
    print(parser.parse().compile())
