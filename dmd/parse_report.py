#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parse the DMD stack trace log format, post-bug 1035570, which landed in Firefox 34.

import sys
import re

# Constants.

trim_print_line_to = 80


# Regular expression for frames we don't care to see.

def boring_frames_regexp():
    boring_frames = ['replace_malloc',
                     'replace_realloc',
                     'replace_calloc',
                     'malloc_zone_malloc',
                     'malloc_zone_calloc',
                     'moz_xmalloc',
                     'moz_xrealloc',
                     'malloc',
                     'realloc',
                     'calloc',
                     'XPT_ArenaMalloc',
                     'XPT_DoHeader',
                     'operator new(unsigned long)',
                     'XREMain::XRE_main(int, char**, nsXREAppData const*)',
                     'XRE_main',
                     'main',
                     '???']

    escaped_boring_frames = []
    for f in boring_frames:
        escaped_boring_frames.append(re.escape(f))

    return '|'.join(escaped_boring_frames)

boring_frames_pattern = re.compile(boring_frames_regexp())


keep_boring_frames = False


# Basic tree transform operations.

def decomma_number_string(s):
    return int(''.join(s.split(',')))

def new_list():
    return []

def append_frame(l, s):
    # XXX It would be nice to remove the trailing address in a non-fragile way.
    if keep_boring_frames or not boring_frames_pattern.match(s):
        l.append(s)
    return l

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
# At each level, there is a triple.
#
# The first element of the triple is the function used to process leaf data, which is a
# fold operation. If this is None, finding any leaf data will throw an exception.
#
# The second element of the triple is a function used to generate the initial value
# for the leaf fold, if the first element isn't None.
#
# The third element is a dictionary used to process any subtrees. (If this element is instead
# None, then finding any subtrees will throw an exception.) The keys are labels on the
# tree node, and the values are a configuration triple for the subtree. If a key is
# encountered that is not present in the configuration map, that entire subtree will
# be ignored.
diff_config = (None, None,
               {'Unreported' : (trace_header_splitter, new_list,
                                {'Allocated at' : (append_frame, new_list, None)})})



blocks_string = 'blocks (requested bytes / slop bytes):'

def new_None():
    return None

def graph_trace_header_splitter(n, s):
    if s.startswith(blocks_string):
        assert n == None
        block_info = []
        for x in s[len(blocks_string):].split(')'):
            if len(x) == 0:
                continue
            x = x.split()
            block_info.append([x[0], int(x[1][1:])])
        return block_info
    return n

live_graph_config = (None, None,
                     {'Live' : (graph_trace_header_splitter, new_None,
                                {'Allocated at' : (append_frame, new_list, None)})})


class ParseTree:
    def __init__(self, config):
        self.data = config[1]() if config[0] else None
        self.subtrees = []
        self.config = config

    def add_data(self, new_data):
        if not self.config[0]:
            raise Exception("Did not expect data " + new_data)
        self.data = self.config[0](self.data, new_data)

    def add_subtree(self, tree_name):
        if not self.config[2]:
            raise Exception("Did not expect any subtrees at all, not even " + tree_name)

        subtree_fun = self.config[2].get(tree_name, None)

        if not subtree_fun:
            # Ignore this subtree.
            return None

        new_tree = ParseTree(subtree_fun)
        self.subtrees.append((tree_name, new_tree))
        return new_tree

    def print_tree(self, indent=''):
        if self.data:
            for d in self.data:
                print indent + str(d)[:trim_print_line_to]
        for (name, t) in self.subtrees:
            print indent + name
            t.print_tree(indent + '  ')
            if len(indent) == 0:
                print


# Create a ParseTree from a file.
def parse_stack_log(f, config):
    blank_line_patt = re.compile('^\w*$')
    outer = ParseTree(config)
    scopes = [outer]

    for l in f:
        # Skip comment lines and blank lines.
        if l.startswith('#'):
            continue

        if blank_line_patt.match(l):
            continue

        # Lines ending in '{' start a new subtree.
        if l[-2] == '{':
            if scopes[-1]:
                subtree = scopes[-1].add_subtree(l[:-2].strip())
            scopes.append(subtree)
            continue

        # Lines ending in '}' end a subtree.
        if l[-2] == '}':
            scopes.pop()
            continue

        # Other lines are data for the current record.
        if scopes[-1]:
            scopes[-1].add_data(l.strip())

    return outer


# Remove some fluff from a ParseTree, and do some basic verification.  This produces
# output in the form expected by diff.py.
def extract_diff_info(tree):
    assert(tree.data == None)

    data = []

    for t in tree.subtrees:
        assert(t[0] == 'Unreported')
        t = t[1]

        # There should be two entries for 'Unreported', the number of blocks and the number of total bytes.
        assert(len(t.data) == 2)
        new_entry = [t.data[0], t.data[1]]

        # There should be exactly one subtree, for 'Allocated at'.
        t = t.subtrees
        assert(len(t) == 1)
        t = t[0]
        assert(len(t) == 2)
        assert(t[0] == 'Allocated at')
        t = t[1]

        # The 'Allocated at' subtree should not have any subtrees.
        assert(len(t.subtrees) == 0)

        # The data of the 'Allocated at' subtree is a list of stack traces.
        new_entry.append(t.data)

        data.append(new_entry)

    return data


class LiveGraphTrace:
    def __init__(self, block, req_bytes, frames):
        self.block = block
        self.req_bytes = req_bytes
        self.frames = frames

# Extract the live graph stack information.
def extract_live_info(tree):
    assert(tree.data == None)

    data = []

    for t in tree.subtrees:
        assert(t[0] == 'Live')
        t = t[1]

        # t.data is a list of block requested-size pairs.
        blocks_info = t.data

        # There should be exactly one subtree, for 'Allocated at'.
        t = t.subtrees
        assert(len(t) == 1)
        t = t[0]
        assert(len(t) == 2)
        assert(t[0] == 'Allocated at')
        t = t[1]

        # The 'Allocated at' subtree should not have any subtrees.
        assert(len(t.subtrees) == 0)

        # The data of the 'Allocated at' subtree is a list of stack traces.
        # Create a trace for every block.
        for [b, rb] in blocks_info:
            data.append(LiveGraphTrace(b, rb, t.data))

    return data



def parse_stack_file(fname, config):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    r = parse_stack_log(f, config)
    f.close()
    return r


def load_diff_info(fname):
    return extract_diff_info(parse_stack_file(fname, diff_config))

def load_live_graph_info(fname, config_keep_boring_frames = False):
    keep_boring_frames = config_keep_boring_frames
    return extract_live_info(parse_stack_file(fname, live_graph_config))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    print load_diff_info(sys.argv[1])
    #print load_live_graph_info(sys.argv[1])[20].frames








