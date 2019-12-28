# DCPU16 C compiler

This is a horrible c compiler targeting the DCPU16 

The reason I am creating this compiler is so I can eventually use it to write
some simple OS for the DCPU16, and because I like C and I can't find anything 
that I can port easily I will just create my own :shrug:

## Working
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
* Global variables
* Multiple compilation units
