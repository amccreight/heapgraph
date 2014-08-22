#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parse the DMD stack trace log format, post-bug 1035570, which landed in Firefox 34.

import sys
import re

blank_line_patt = re.compile('^\w*$')

trim_print_line_to = 80


# Tree folding operations.

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
        subtree_fun = f[2].get(subtree[0], None)
        if not subtree_fun:
            continue
        l2.append((subtree[0], tree_map(subtree[1], subtree_fun)))

    return (l1, l2)


# Standard tree splitting operations.

def invocation_splitter(l, s):
    l.append(s.split(' = '))
    return l

def new_list():
    return []

def expect_no_data(x, y):
    raise Exception("Did not expect: " + str(y))

def list_append(l, s):
    l.append(s)
    return l

def do_nothing(x, y):
    return

def decomma_number_string(s):
    return int(''.join(s.split(',')))

# Regexps for trace headers.
first_line_patt = re.compile('\~?(\d+) blocks? in heap block record.*')
second_line_patt = re.compile('\~?([0-9,]+) bytes \(~?[0-9,]+ requested')

def trace_header_splitter(l, s):
    h = None
    flm = first_line_patt.match(s)
    if flm:
        h = decomma_number_string(flm.group(1))
    else:
        slm = second_line_patt.match(s)
        if slm:
            h = decomma_number_string(slm.group(1))

    if h:
        l.append(h)
    return l


# You can configure the parser by passing in different things for this nested data type.
# At each level, there is a triple. The first is the function used to process leaf data,
# which is a fold operation. The second is the function used to generate the initial value
# for the leaf fold. The third is a dictionary used to process any tree data. The key is
# the label on the tree node, and the value is another triple describing the desired
# behavior. If a key is encountered that is not present in the configuration map, that
# entire subtree will be ignored.
diff_config = (expect_no_data, None,
               {'Unreported' : (trace_header_splitter, new_list,
                                {'Allocated at' : (list_append, new_list, None)})})
# If you want to filter the stack frames somehow, change the |do_nothing| function for 'Allocated at'.



applier = (None, {'Invocation' : (do_nothing, None),
                  'Unreported' : (do_nothing,
                                  {'Allocated at' : (do_nothing, None)})})


# demangle_tree takes the tree output, and produces a less weird data structure as output,
# by removing various empty stuff.  it produces output in the form expected by diff.py.
def demangle_tree(tree):
    tree = tree_map(tree, diff_config)
    assert(tree[0] == None)
    tree = tree[1]

    data = []

    for r in tree:
        entry = r[1]

        # This is what you get for creating a Lisp-y data structure.
        assert(len(entry[0]) == 2)
        assert(len(entry[1]) == 1)
        assert(len(entry[1][0]) == 2)
        assert(len(entry[1][0][1]) == 2)
        assert(len(entry[1][0][1][1]) == 0)

        new_entry = [entry[0][0], entry[0][1], entry[1][0][1][0]]
        data.append(new_entry)

    return data


def print_tree(tree, indent=''):
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


def demangle_parse_stack_file(fname):
    return demangle_tree(parse_stack_file(fname))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    demangle_parse_stack_file(sys.argv[1])








