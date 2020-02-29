from frontend.optimizer import Optimizer
from frontend.parser import Parser

from backend.dcpu16.translator import Dcpu16Translator

code = """
int add(int a, int b) {
    return a + b;
}

void test() {
    int a;
    break;
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
if p.got_errors:
    exit(-1)

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
