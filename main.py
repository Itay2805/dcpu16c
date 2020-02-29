#!/usr/bin/python3

from cc.parser import Parser
from cc.optimizer import Optimizer
from cc.translator import Translator

import sys

if __name__ == '__main__':
    c_files = []
    asm_files = []

    stop_at_comp = False

    for file in sys.argv:
        if file.endswith('.c'):
            c_files.append(file)
        elif file.endswith('.asm'):
            asm_files.append(file)
        elif file == '-S':
            stop_at_comp = True

    for cf in c_files:
        with open(cf, 'r') as f:
            code = f.read()

        p = Parser(code, filename=cf)
        p.parse()

        opt = Optimizer(p)
        opt.optimize()

        trans = Translator(p)
        trans.translate()

        insts = trans.get_instructions()

        print('\n'.join(insts))

