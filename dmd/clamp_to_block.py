#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Look for address-like substrings, and clamp them to the start of
# blocks they are in, where the set of allocated blocks is defined by
# a stack trace file.

import sys
import parse_report



def print_frames(frames, indent, num_frames_to_print):
    num_printed = 0
    for f in frames:
        print indent, f
        num_printed += 1
        if num_printed == num_frames_to_print:
            break


# Start is the address of the first byte of the block, while end is
# the first byte past the end of the block.
class AddrRange:
    def __init__(self, block, length, frames):
        self.block = block
        self.start = int(block, 16)
        self.length = length
        self.frames = frames

    def print_it(self, frames_indent, num_frames_to_print):
        print self.block, self.start, self.length
        print_frames(self.frames, frames_indent, num_frames_to_print)

    def end(self):
        return self.start + self.length


def do_stuff(trace_file_name):
    raw_traces = parse_report.load_live_graph_info(trace_file_name, True)

    ranges = []

    for t in raw_traces:
        for b in t.blocks:
            ranges.append(AddrRange(b, t.req_bytes, t.frames))

    ranges.sort(key=lambda r: r.start)

    # Remove overlapping blocks.
    new_ranges = []
    last_overlapped = False

    for curr_range in ranges:
        if len(new_ranges) == 0:
            new_ranges.append(curr_range)
            continue

        prev_range = new_ranges[-1]
        assert prev_range.start < curr_range.start

        if curr_range.start < prev_range.end():
            last_overlapped = True
            # Keep the block at the end that ends the latest.
            if prev_range.end() < curr_range.end():
                new_ranges[-1] = curr_range
        else:
            if last_overlapped:
                new_ranges[-1] = curr_range
            else:
                new_ranges.append(curr_range)
            last_overlapped = False

    if last_overlapped:
        new_ranges.pop()
        last_overlapped = False

    print 'Removed', len(ranges) - len(new_ranges), 'overlapping blocks, leaving', len(new_ranges)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    do_stuff(sys.argv[1])




