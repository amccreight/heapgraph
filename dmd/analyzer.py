#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Try to find out something useful about a particular object.

import sys
import argparse
import json
import re

# The DMD output version this script handles.
outputVersion = 1

# If --ignore-alloc-fns is specified, stack frames containing functions that
# match these strings will be removed from the *start* of stack traces. (Once
# we hit a non-matching frame, any subsequent frames won't be removed even if
# they do match.)
allocatorFns = [
    'malloc (',
    'replace_malloc',
    'replace_calloc',
    'replace_realloc',
    'replace_memalign',
    'replace_posix_memalign',
    'malloc_zone_malloc',
    'moz_xmalloc',
    'moz_xcalloc',
    'moz_xrealloc',
    'operator new(',
    'operator new[](',
    'g_malloc',
    'g_slice_alloc',
    'callocCanGC',
    'reallocCanGC',
    'vpx_malloc',
    'vpx_calloc',
    'vpx_realloc',
    'vpx_memalign',
    'js_malloc',
    'js_calloc',
    'js_realloc',
    'pod_malloc',
    'pod_calloc',
    'pod_realloc',
    'nsTArrayInfallibleAllocator::Malloc',
    # This one necessary to fully filter some sequences of allocation functions
    # that happen in practice. Note that ??? entries that follow non-allocation
    # functions won't be stripped, as explained above.
    '???',
]

####

# Command line arguments

def range_1_24(string):
    value = int(string)
    if value < 1 or value > 24:
        msg = '{:s} is not in the range 1..24'.format(string)
        raise argparse.ArgumentTypeError(msg)
    return value

parser = argparse.ArgumentParser(description='Analyze the heap graph to find out things about an object.')

parser.add_argument('file_name',
                    help='clamped DMD log file name')

parser.add_argument('block',
                    help='address of the block of interest')

parser.add_argument('--referrers', dest='referrers', action='store_true',
                    default=False,
                    help='Print out information about blocks holding onto the object. (default)')

# XXX not updated yet
#parser.add_argument('--flood-graph', dest='flood_graph', action='store_true',
#                    default=False,
#                    help='Print out blocks reachable from a particular block.')

parser.add_argument('--stack-frame-length', '-sfl', type=int,
                    default=150,
                    help='Number of characters to print from each stack frame')

parser.add_argument('-a', '--ignore-alloc-fns', action='store_true',
                    help='ignore allocation functions at the start of traces')

parser.add_argument('-f', '--max-frames', type=range_1_24,
                    help='maximum number of frames to consider in each trace')

####


class BlockData:
    def __init__(self, json_block):
        self.addr = json_block['addr']

        if 'contents' in json_block:
            contents = json_block['contents']
        else:
            contents = []
        self.contents = []
        for c in contents:
            self.contents.append(int(c, 16))

        self.req_size = json_block['req']

        self.alloc_stack = json_block['alloc']


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


def print_trace_segment(args, stacks, block):
    (traceTable, frameTable) = stacks

    for l in traceTable[block.alloc_stack]:
        print ' ', frameTable[l][5:args.stack_frame_length]


def show_flood_graph(args, block_edges, traces, req_sizes, block):
    [reachable, ids] = flood_graph(block, block_edges)

    for r in reachable:
        edge_ids = []
        for e in block_edges.get(r, set([])):
            edge_ids.append(str(ids[e]))
        edge_ids = sorted(edge_ids)

        print str(ids[r]), 'addr=', r, 'size=', req_sizes[r], ' -->', ', '.join(edge_ids)
        print_trace_segment(args, traces, r)
        print


def show_referrers(args, blocks, stacks, block):
    referrers = {}

    for b, data in blocks.iteritems():
        which_edge = 0
        for e in data.contents:
            if e == block:
                referrers.setdefault(b, []).append(8 * which_edge)
            which_edge += 1

    for r in referrers:
        print blocks[r].addr, 'size =', blocks[r].req_size,
        plural = 's' if len(referrers[r]) > 1 else ''
        sys.stdout.write(' at byte offset' + plural + ' ' + (', '.join(str(x) for x in referrers[r])))
        print
        print_trace_segment(args, stacks, blocks[r])
        print


def cleanupTraceTable(args, frameTable, traceTable):
    # Remove allocation functions at the start of traces.
    if args.ignore_alloc_fns:
        # Build a regexp that matches every function in allocatorFns.
        escapedAllocatorFns = map(re.escape, allocatorFns)
        fn_re = re.compile('|'.join(escapedAllocatorFns))

        # Remove allocator fns from each stack trace.
        for traceKey, frameKeys in traceTable.items():
            numSkippedFrames = 0
            for frameKey in frameKeys:
                frameDesc = frameTable[frameKey]
                if re.search(fn_re, frameDesc):
                    numSkippedFrames += 1
                else:
                    break
            if numSkippedFrames > 0:
                traceTable[traceKey] = frameKeys[numSkippedFrames:]

    # Trim the number of frames.
    for traceKey, frameKeys in traceTable.items():
        if len(frameKeys) > args.max_frames:
            traceTable[traceKey] = frameKeys[:args.max_frames]


def loadGraph(options):
    sys.stderr.write('Loading file.\n')
    with open(options.file_name, 'rb') as f:
        j = json.load(f)

    if j['version'] != outputVersion:
        raise Exception("'version' property isn't '{:d}'".format(outputVersion))

    invocation = j['invocation']
    sampleBelowSize = invocation['sampleBelowSize']
    heapIsSampled = sampleBelowSize > 1
    if heapIsSampled:
        raise Exception("Heap analysis is not going to work with sampled blocks.")

    block_list = j['blockList']
    blocks = {}

    for json_block in block_list:
        blocks[int(json_block['addr'], 16)] = BlockData(json_block)

    traceTable = j['traceTable']
    frameTable = j['frameTable']

    cleanupTraceTable(options, frameTable, traceTable)

    return (blocks, (traceTable, frameTable))


def analyzeLogs():
    options = parser.parse_args()

    (blocks, stacks) = loadGraph(options)

    block = int(options.block, 16)

    if not block in blocks:
        print 'Object', block, 'not found in traces.'
        print 'It could still be the target of some nodes.'
        return

    #if options.flood_graph:
    #    show_flood_graph(options, block_edges, traces, req_sizes, block)
    #    return

    show_referrers(options, blocks, stacks, block)


if __name__ == "__main__":
    analyzeLogs()

