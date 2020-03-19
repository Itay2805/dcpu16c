// will put the main as the first function in the file
void main();

// simple display driver
static char* video_ram = (char*)0x8000;
static int x = 0;
static int y = 0;

static void putc(int c) {
//    if (c != '\n') {
//        *video_ram[x + y * 32] = ((0 << 0x8) | (3 << 0xc)) | c;
//    }

    c = c + 5;

//    x++;
//    if (x == 32) {
//        x = 0;
//        y++;
//    }
}

// print something
//void main() {
//    putc('H');
//    putc('E');
//    putc('L');
//    putc('L');
//    putc('O');
//}
