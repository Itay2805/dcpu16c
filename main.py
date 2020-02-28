from frontend.optimizer import Optimizer
from frontend.parser import Parser

from backend.dcpu16.translator import Dcpu16Translator

code = """
typedef union add {
    struct as_stct {
        int a;
        int b;
    } as_stct;
    int as_array[2];
    int a;
} add_t;

void test() {
    add_t add;
    add.as_stct.a = 123;
    add.as_array[0] = 123;
    add.a = 123;
    add.as_array[1] = 123;
}
"""

print("============================")
print(" Code ")
print("============================")
print(code)

#
# Parse the code
#
p = Parser(code)
p.parse()
assert not p.got_errors

print()
print("============================")
print(" AST ")
print("============================")
print('\n\n'.join(map(str, p.func_list)))

#
# Optimize the AST
#
opt = Optimizer(p)
opt.optimize()

print()
print("============================")
print(" Optimized AST ")
print("============================")
print('\n\n'.join(map(str, p.func_list)))

#
# Translate it to assembler
#
trans = Dcpu16Translator(p)
trans.translate()

print()
print("============================")
print(" Assembly ")
print("============================")
print('\n'.join(trans.get_instructions()))
