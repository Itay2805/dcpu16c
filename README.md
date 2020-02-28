# DCPU16 C compiler

This is a horrible c compiler targeting the DCPU16 

The reason I am creating this compiler is so I can eventually use it to write
some simple OS for the DCPU16, and because I like C and I can't find anything 
that I can port easily I will just create my own :shrug:

## Example 

```c
int add(int a, int b) {
    return a + b;
}

int mul(int num, int times) {
    int res = 0;
    while(times--) {
        res += num;
    }
    return res;
}
```

would compile to
```
:add
    SET PUSH, J
    SET J, SP
    SET A, [J + 1]
    ADD A, [J + 2]
    SET SP, J
    SET J, POP
    SET PC, POP


:mul
    SET PUSH, J
    SET J, SP
    SUB SP, 2
    SET [J - 1], 0
    :L1
    SET [J - 2], [J + 2]
    SUB [J + 2], 1
    IFE [J - 2], 0
    SET PC, L0
    ADD [J - 1], [J + 1]
    SET PC, L1
    :L0
    SET A, [J - 1]
    SET SP, J
    SET J, POP
    SET PC, POP
```

As you can see the assembly is actually quite nicely optimized, You can also use the `register` storage modifier on 
integer variables to tell the compiler to try and use registers for them, if you do that correctly it can actually
generate some really nicely optimized code :)

the way to get the best performance is to have assembly functions as `regcall` but to not use it for c functions since 
the code gen for it is horrible right now.

## ABI
### Calling convention
The compiler is compliant to the [0x10c Standards Committee ABI](https://github.com/0x10cStandardsCommittee/0x10c-Standards/blob/master/ABI/ABI%20draft%202.txt) 
(Supporting both stackcall and regcall). We do use the function Prologue and Epilogue and shown in the [first draft](https://github.com/0x10cStandardsCommittee/0x10c-Standards/blob/master/ABI/Draft_ABI_1.txt#L49-L70), 
this does not affect calling functions which do not implement that because it is only related to code generation inside
the current function.

## Working
* Functions (support bot for regcall and stackcall)
* Variables (only at the start of functions)
* All of the arithmetic/bitwise operators
* While and do while loops
* If/Else (No code gen yet)
* Stack arrays
