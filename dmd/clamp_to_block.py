#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Look for address-like substrings, and clamp them to the start of
# blocks they are in, where the set of allocated blocks is defined by
# a stack trace file.

import sys
import parse_report
import bisect
import re


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


def load_block_ranges(trace_file_name):
    sys.stderr.write('Parsing input file. ')
    raw_traces = parse_report.load_live_graph_info(trace_file_name, True)

    ranges = []

    sys.stderr.write('Building address range array. ')
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

    sys.stderr.write('Removed ' + str(len(ranges) - len(new_ranges)) + ' overlapping blocks, leaving ' + str(len(new_ranges)) + '. Done loading.\n')

    return new_ranges


# Address is an address as a hex string.
def get_clamped_address(block_ranges, address):
    address = int(address, 16)

    low = 0
    high = len(block_ranges) - 1
    while low <= high:
        mid = low + (high - low) / 2
        if address < block_ranges[mid].start:
            high = mid - 1
            continue
        if address >= block_ranges[mid].end():
            low = mid + 1
            continue
        return block_ranges[mid].block

    return None


hit_miss = [0, 0, 0]


def clamp_repl(block_ranges, match):
    clamped = get_clamped_address(block_ranges, match.group(0))
    if clamped:
        if clamped == match.group(0):
            #sys.stderr.write('IDENTITY HIT ' + clamped + '\n')
            hit_miss[2] += 1
        else:
            #sys.stderr.write('HIT ' + match.group(0) + ' --> ' + clamped + '\n')
            hit_miss[0] += 1
        return clamped
    else:
        #sys.stderr.write('MISS ' + match.group(0) + '\n')
        hit_miss[1] += 1
        return match.group(0)


address_patt = re.compile('0x[0-9a-f]+')

def clamp_file_addresses(live_file_name, source_file_name):
    block_ranges = load_block_ranges(live_file_name)

    try:
        f = open(source_file_name, 'r')
    except:
        sys.stderr.write('Error opening file ' + source_file_name + '\n')
        exit(-1)

    for l in f:
        print re.sub(address_patt, lambda match: clamp_repl(block_ranges, match), l),

    f.close()

    sys.stderr.write('Num hits: ' + str(hit_miss[0]) + '  Num identity hits:' + str(hit_miss[2]) + '  Num misses: ' + str(hit_miss[1]) + '\n')


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    clamp_file_addresses(sys.argv[1], sys.argv[2])
