#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Parse the trace-malloc types.dat file, which is used to infer types of objects from the stack traces of their allocation.


import sys
import re


def parse_stacks_to_types(f):
    stack_patterns = []

    for l in f:
        # Comment line.
        if l[0] == '#':
            continue
        # Blank line.
        if len(l) == 1:
            continue
        if l[0] == '<':
            currType = l[1:l.rfind('>')]
            stack_patterns.append([currType])
        else:
            stack_patterns[-1].append(l[:-1])

    print stack_patterns

def parse_stacks_to_type_file(fname):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    r = parse_stacks_to_types(f)
    f.close()

    return r


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    parse_stacks_to_type_file(sys.argv[1])

