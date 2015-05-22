#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Try to find a particular block you are looking for, based on some properties it has.

import sys
import re
import argparse
import parse_traces


parser = argparse.ArgumentParser(description='Find objects matching certain parameters.')

parser.add_argument('stack_trace_file_name',
                    help='allocation stack trace file name')

parser.add_argument('--size', '-s', dest='size', type=int,
                    help='Requested size')

# XXX Need to improve the parser to support this. This is useful because you should know
# from the bloat log how many of a particular class are present.
#parser.add_argument('--num-blocks', '-nb', dest='num_blocks', type=int,
#                    help='Number of blocks allocated with the stack')

parser.add_argument('--max-stack-match-depth', '-msmd', dest='max_stack_depth', type=int,
                    default=2,
                    help='Don\'t print matches that match at a deeper stack frame than this.')

parser.add_argument('--stack-frame-length', '-sfl', dest='stack_frame_length', type=int,
                    default=200,
                    help='Number of characters to print from each stack frame')


frame_regexp = 'HTMLTrackElement::LoadResource'
frame_pattern = re.compile(frame_regexp)


def print_trace_segment(args, traces, block, depth):
    for l in traces[block][:depth]:
        print ' ', l[:args.stack_frame_length]

def analyzeLogs():
    args = parser.parse_args()

    # XXX Make this use parse_report.load_live_graph_info, then generate the two dicts from there.
    assert False
    [traces, req_sizes] = parse_traces.parse_stack_file(args.stack_trace_file_name)

    if not args.size:
        print 'Expected --size argument'
        exit(-1)

    block_matches = []

    for b, tr in traces.iteritems():
        if args.size == req_sizes[b]:
            which_frame = 0
            for f in tr:
                which_frame += 1
                frame_match = frame_pattern.search(f)
                if frame_match:
                    block_matches.append([which_frame, b])
                    break

    block_matches = sorted(block_matches)

    for [which_frame, b] in block_matches:
        if which_frame > args.max_stack_depth:
            break
        print 'block:', b
        print_trace_segment(args, traces, b, which_frame)
        print

if __name__ == "__main__":
    analyzeLogs()

