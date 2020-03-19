# DCPU16 C compiler

This is a horrible c compiler targeting the DCPU16 

The reason I am creating this compiler is so I can eventually use it to write
some simple OS for the DCPU16, and because I like C and I can't find anything 
that I can port easily I will just create my own :shrug:

## Invoking

simply run 
```shell script
./main.py <files>
```

### Arguments
#### Stop at assembly stage - `-S`
This will create `.dasm` file for every input file. This will not generate any assembly.

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

## ABI
### Calling convention
The compiler is compliant to the [0x10c Standards Committee ABI](https://github.com/0x10cStandardsCommittee/0x10c-Standards/blob/master/ABI/ABI%20draft%202.txt) 
(Supporting both stackcall and regcall). We do use the function Prologue and Epilogue and shown in the [first draft](https://github.com/0x10cStandardsCommittee/0x10c-Standards/blob/master/ABI/Draft_ABI_1.txt#L49-L70), 
this does not affect calling functions which do not implement that because it is only related to code generation inside
the current function.

To specify which calling convention to use simply add `__regcall` or `__stackcall` before the function name, the default
calling convention is `__stackcall`.

## Working
* multiple compilation units
    * will link everything correctly
* typedefs 
* structs and unions
    * can be nested
    * still no support for anonymous structs/unions
    * still no support for packed structs
* Functions and function calls (support bot for regcall and stackcall)
    * regcall call is still wip 
* Variables (only at the start of functions)
    * register storage class is supported
* Global variables
* Fixed size arrays
* All of the arithmetic/bitwise operators
* While loops with break and continue
* if/else (No code gen yet)
