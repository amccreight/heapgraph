#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parsing the simple raw block graph format.

import sys

def parse_block_graph(f):
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
        edges = set(l[2:])
        block_edges[b] = edges

        count += 1

    return [block_lens, block_edges]


def parse_block_graph_file(fname):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    r = parse_block_graph(f)
    f.close()

    return r


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    parse_block_graph_file(sys.argv[1])

