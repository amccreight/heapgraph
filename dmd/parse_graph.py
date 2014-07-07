#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parsing the simple raw block graph format.

import sys

def parse_block_graph(f, set_edges):
    count = 0

    block_lens = {}
    block_edges = {}

    for l in f:
        l = l.split()
        b = l[0]

        assert(not b in block_lens)
        block_len = int(l[1])
        block_lens[b] = block_len

        assert(not b in block_edges)
        if set_edges:
            edges = set(l[2:])
        else:
            edges = l[2:]
        block_edges[b] = edges

        count += 1

    return [block_lens, block_edges]


def parse_block_graph_file(fname, set_edges):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    r = parse_block_graph(f, set_edges)
    f.close()

    return r

def compute_size(r):
    [block_lens, block_edges] = r
    total_words = 0
    for b, e in block_edges.iteritems():
        total_words += 2 + len(e)
    print total_words * 8

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    r = parse_block_graph_file(sys.argv[1], True)
    compute_size(r)
