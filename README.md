# DCPU16 C compiler

This is a horrible c compiler targeting the DCPU16 

The reason I am creating this compiler is so I can eventually use it to write
some simple OS for the DCPU16, and because I like C and I can't find anything 
that I can port easily I will just create my own :shrug:

## Example 

```c
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
```

would compile to
```
JSR main
:_l0
	SET PC, _l0

:videoram
DAT 32768

:main
	SET X, SP
	SUB SP, 1
	SET [SP], 72
	JSR putc
	ADD SP, 1
	SUB SP, 1
	SET [SP], 65
	JSR putc
	ADD SP, 1
	SUB SP, 1
	SET [SP], 73
	JSR putc
	ADD SP, 1
	SET PC, POP

:putc
	SET X, SP
	SET A, [videoram]
	SET [A], 3840
	SET B, [X + 1]
	BOR [A], B
	ADD [videoram], 1
	SET PC, POP
```

the main problem for now is that function calls are really not efficient, would probably want to add a pass to remove
duplicate 
```
ADD SP, 1
SUB SP, 1
```

the way to get the best performance is to have assembly functions as `regcall` but to not use it for c functions since 
the code gen for it is horrible right now 

## Working
* Global variables
* Functions and function calls
    * support for stack call
    * support for register call (code gen for regcall functions is pretty shitty at the moment)     
* Variables (must be declared at start of function)
* All binary and unary operators
    * pointer arith is kinda broken on types which are not 16bit
* type checking
* if and else
* while loop
* return
* pointers
* casts

## TODO
* Structs, Enums and Unions
* Multiple compilation units
