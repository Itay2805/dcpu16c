#!/usr/bin/python3

from cc.parser import Parser
from cc.optimizer import Optimizer
from cc.translator import Translator

from asm.assembler import Assembler

from link.linker import Linker, BinaryType

import sys

if __name__ == '__main__':
    c_files = []
    asm_files = []

    stop_at_comp = False

    for file in sys.argv:
        if file.endswith('.c'):
            c_files.append(file)
        elif file.endswith('.dasm'):
            asm_files.append(file)
        elif file == '-S':
            stop_at_comp = True

    objects = []

    got_errors = False

    for cf in c_files:
        with open(cf, 'r') as f:
            code = f.read()

        p = Parser(code, filename=cf)
        p.parse()

        if not p.got_errors:
            opt = Optimizer(p)
            opt.optimize()

            trans = Translator(p)
            trans.translate()

            insts = trans.get_instructions()
            code = '\n'.join(insts)

            if stop_at_comp:
                with open(cf + '.dasm', 'w') as f:
                    f.write(code)
            else:
                asm = Assembler(code, cf)
                asm.parse()
                asm.fix_labels()

                if not asm.got_errors:
                    objects.append(asm.get_object())
                else:
                    got_errors = True
        else:
            got_errors = True

    for af in asm_files:
        with open(af, 'r') as f:
            code = f.read()

        if not stop_at_comp:
            asm = Assembler(code, filename=af)
            asm.parse()
            asm.fix_labels()
            if not asm.got_errors:
                objects.append(asm.get_object())
            else:
                got_errors = True

    if stop_at_comp or got_errors:
        exit(0)

    # Link it all
    linker = Linker()
    for object in objects:
        linker.append_object(object)

    linker.link(BinaryType.RAW, {})

    if not linker.got_errors:
        for word in linker.get_words():
            print(hex(word)[2:].zfill(4))
