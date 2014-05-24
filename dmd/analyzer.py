#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Try to find out something useful about a particular object.

import sys
import parse_graph
import parse_traces




def flood_graph(start, edges):
    visited_order = []
    visited = set([start])
    work_list = [start]
    ids = {}
    num_visited = 0

    while len(work_list) != 0:
        x = work_list.pop()
        visited_order.append(x)
        num_visited += 1
        ids[x] = num_visited
        assert(x in visited)
        if not x in edges:
            continue

        for e in edges[x]:
            if e in visited:
                continue
            visited.add(e)
            work_list.append(e)

    return [visited_order, ids]


def doStuff():
    if len(sys.argv) < 4:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    [block_lens, block_edges] = parse_graph.parse_block_graph_file(sys.argv[1])
    [traces, req_sizes] = parse_traces.parse_stack_file(sys.argv[2])

    obj = sys.argv[3]

    if not obj in traces:
        print 'Object', obj, 'not found in traces.'

    if not obj in block_edges:
        print 'Object', obj, 'not found in edges.'
        print 'It could still be the target of some nodes.'

    [reachable, ids] = flood_graph(obj, block_edges)

    for r in reachable:
        edge_ids = []
        for e in block_edges.get(r, set([])):
            edge_ids.append(str(ids[e]))
        edge_ids = sorted(edge_ids)

        print str(ids[r]), 'addr=', r, 'size=', req_sizes[r], ' -->', ', '.join(edge_ids)
        for l in traces[r][:4]:
            print ' ', l[:150]
        print

#        for b, stack in traces.iteritems():
#            print b, ':', req_sizes[b]
#            for l in stack:
#                print ' ', l[:max_frame_len]



if __name__ == "__main__":
    doStuff()

