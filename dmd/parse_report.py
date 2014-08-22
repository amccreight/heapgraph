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




class ParseTree:
    def __init__(self):
        self.data = []
        self.subtrees = []

    def add_data(self, new_data):
        self.data.append(new_data)

    def add_subtree(self, tree_name):
        new_tree = ParseTree()
        self.subtrees.append((tree_name, new_tree))
        return new_tree

    def print_tree(self, indent=''):
        for d in self.data:
            print indent + d[:trim_print_line_to]
        for (name, t) in self.subtrees:
            print indent + name
            t.print_tree(indent + '  ')
            if len(indent) == 0:
                print

    def map_tree(self, config):
        fold_0 = config[1]() if config[1] else None
        l1 = reduce(config[0], self.data, fold_0)
        l2 = []
        for t in self.subtrees:
            subtree_fun = config[2].get(t[0], None)
            if not subtree_fun:
                continue
            l2.append((t[0], t[1].map_tree(subtree_fun)))

        return (l1, l2)



# demangle_tree takes the tree output, and produces a less weird data structure as output,
# by removing various empty stuff.  it produces output in the form expected by diff.py.
def demangle_tree(tree):
    tree = tree.map_tree(diff_config)
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


def parse_stack_log(f):
    outer = ParseTree()
    scopes = [outer]

    for l in f:
        # Skip comment lines and blank lines.
        if l.startswith('#'):
            continue

        if blank_line_patt.match(l):
            continue

        # Lines ending in '{' start a new subtree.
        if l[-2] == '{':
            subtree = scopes[-1].add_subtree(l[:-2].strip())
            scopes.append(subtree)
            continue

        # Lines ending in '}' end a subtree.
        if l[-2] == '}':
            scopes.pop()
            continue

        # Other lines are data for the current record.
        scopes[-1].add_data(l.strip())

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








