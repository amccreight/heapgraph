#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Try to find out something useful about a particular object.

import sys
import argparse

import parse_graph
import parse_traces

####

# Command line arguments

parser = argparse.ArgumentParser(description='Analyze the heap graph to find out things about an object.')

parser.add_argument('block_graph_file_name',
                    help='heap block graph file name')

parser.add_argument('stack_trace_file_name',
                    help='allocation stack trace file name')

parser.add_argument('block',
                    help='address of the block of interest')

parser.add_argument('--referrers', dest='referrers', action='store_true',
                    default=False,
                    help='Print out information about blocks holding onto the object. (default)')

parser.add_argument('--flood-graph', dest='flood_graph', action='store_true',
                    default=False,
                    help='Print out blocks reachable from a particular block.')






####

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


def print_trace_segment(traces, block):
    for l in traces[block][:4]:
        print ' ', l[:150]


def show_flood_graph(block_edges, traces, req_sizes, block):
    [reachable, ids] = flood_graph(block, block_edges)

    for r in reachable:
        edge_ids = []
        for e in block_edges.get(r, set([])):
            edge_ids.append(str(ids[e]))
        edge_ids = sorted(edge_ids)

        print str(ids[r]), 'addr=', r, 'size=', req_sizes[r], ' -->', ', '.join(edge_ids)
        print_trace_segment(traces, r)
        print


#        for b, stack in traces.iteritems():
#            print b, ':', req_sizes[b]
#            for l in stack:
#                print ' ', l[:max_frame_len]


def show_referrers(block_edges, traces, req_sizes, block):
    referrers = set([])

    for b, bedges in block_edges.iteritems():
        if block in bedges:
            referrers.add(b)

    for r in referrers:
        print r, 'size =', req_sizes[r]
        print_trace_segment(traces, r)
        print

def analyzeLogs():
    args = parser.parse_args()

    [block_lens, block_edges] = parse_graph.parse_block_graph_file(args.block_graph_file_name)
    [traces, req_sizes] = parse_traces.parse_stack_file(args.stack_trace_file_name)

    block = args.block

    if not block in traces:
        print 'Object', block, 'not found in traces.'

    if not block in block_edges:
        print 'Object', block, 'not found in edges.'
        print 'It could still be the target of some nodes.'

    if args.flood_graph:
        show_flood_graph(block_edges, traces, req_sizes, block)
        return

    show_referrers(block_edges, traces, req_sizes, block)


if __name__ == "__main__":
    analyzeLogs()

