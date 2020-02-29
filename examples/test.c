int main();

int mul(int _a, int _times) {
    register int num = 0;
    register int a = _a;
    register int times = _times;
    while (times--) {
        num += a;
    }
    return num;
}

int main() {
    return mul(5, 5);
}
