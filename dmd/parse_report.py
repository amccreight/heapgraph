#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parse the DMD stack trace log format, post-bug 1035570, which landed in Firefox 34.

import sys
import re

blank_line_patt = re.compile('^\w*$')

trim_print_line_to = 80


def tree_apply(tree, f):
    for header_line in tree[0]:
        f[0](header_line)
    for subtree in tree[1]:
        tree_apply(subtree[1], f[1][subtree[0]])

def tree_map(tree, f):
    v = f[1]() if f[1] else None
    l1 = reduce(f[0], tree[0], v)
    l2 = []
    for subtree in tree[1]:
        l2.append((subtree[0], tree_map(subtree[1], f[2][subtree[0]])))

    return (l1, l2)


def invocation_splitter(l, s):
    l.append(s.split(' = '))
    return l


def new_list():
    return []

def whatever(x, y):
    return

applier = (None, {'Invocation' : (whatever, None),
                  'Unreported' : (whatever,
                                  {'Allocated at' : (whatever, None)})})

mapper = (None, None, {'Invocation' : (invocation_splitter, new_list, None),
                       'Unreported' : (whatever, None,
                                       {'Allocated at' : (whatever, None, None)})})



def print_tree(tree, indent=''):
    print tree_map(tree, mapper)
    return

    for header_line in tree[0]:
        print indent + header_line[:trim_print_line_to]
    for subtree in tree[1]:
        print indent + subtree[0]
        print_tree(subtree[1], indent + '  ')
        if len(indent) == 0:
            print



def scope_frame():
    return ([], [])

def parse_stack_log(f):
    outer = scope_frame()
    scopes = [outer]

    count = 0

    for l in f:
        # Skip comment lines and blank lines.
        if l.startswith('#'):
            continue

        if blank_line_patt.match(l):
            continue

        # Lines ending in '{' start a new section.
        if l[-2] == '{':
            new_section = l[:-2].strip()
            new_scope = scope_frame()
            scopes[-1][1].append((new_section, new_scope))
            scopes.append(new_scope)
            continue

        # Lines ending in '}' end a section.
        if l[-2] == '}':
            scopes.pop()
            if len(scopes) == 1:
                count += 1
                if count == 3:
                    break
            continue

        # Other lines are data for the current record.
        scopes[-1][0].append(l.strip())

    return outer


def parse_stack_file(fname):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    r = parse_stack_log(f)
    f.close()
    return r


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    print_tree(parse_stack_file(sys.argv[1]))








