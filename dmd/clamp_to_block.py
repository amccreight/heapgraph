#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Look for address-like substrings, and clamp them to the start of
# blocks they are in, where the set of allocated blocks is defined by
# a stack trace file.

import json
import gzip
import sys
import tempfile
import shutil


# The DMD output version this script handles.
outputVersion = 4


# Start is the address of the first byte of the block, while end is
# the first byte past the end of the block.
class AddrRange:
    def __init__(self, block, length):
        self.block = block
        self.start = int(block, 16)
        self.length = length

    def end(self):
        return self.start + self.length


def load_block_ranges(block_list):
    ranges = []

    for block in block_list:
        ranges.append(AddrRange(block['addr'], block['req']))

    ranges.sort(key=lambda r: r.start)

    # Make sure there are no overlapping blocks.
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

    assert len(ranges) == len(new_ranges) # Shouldn't have any overlapping blocks.

    return new_ranges


# Search the block ranges array for a block that address points into.
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


# An address is either already a pointer to a block,
# a pointer into a block,
# a non-null pointer to a block,
# or a null pointer to a block.
hit_miss = [0, 0, 0, 0]


def clamp_address(block_ranges, address):
    clamped = get_clamped_address(block_ranges, address)
    if clamped:
        if clamped == address:
            hit_miss[0] += 1
        else:
            hit_miss[1] += 1
        return clamped
    else:
        if address == '0':
            hit_miss[3] += 1
        else:
            hit_miss[2] += 1
        return '0'


def clamp_block_contents(block_ranges, block_list):
    for block in block_list:
        # Small blocks don't have any contents.
        if not 'contents' in block:
            continue

        new_contents = []
        for address in block['contents']:
            new_contents.append(clamp_address(block_ranges, address))

        block['contents'] = new_contents

    sys.stderr.write('Results:\n')
    sys.stderr.write('  Number of pointers already pointing to start of blocks: ' + str(hit_miss[0]) + '\n')
    sys.stderr.write('  Number of pointers clamped to start of blocks: ' + str(hit_miss[1]) + '\n')
    sys.stderr.write('  Number of non-null pointers not pointing into blocks: ' + str(hit_miss[2]) + '\n')
    sys.stderr.write('  Number of null pointers: ' + str(hit_miss[3]) + '\n')

def clamp_file_addresses(input_file_name):
    sys.stderr.write('Loading file.\n')
    isZipped = input_file_name.endswith('.gz')
    opener = gzip.open if isZipped else open

    with opener(input_file_name, 'rb') as f:
        j = json.load(f)

    if j['version'] != outputVersion:
        raise Exception("'version' property isn't '{:d}'".format(outputVersion))

    invocation = j['invocation']
    sampleBelowSize = invocation['sampleBelowSize']
    heapIsSampled = sampleBelowSize > 1
    if heapIsSampled:
        raise Exception("Heap analysis is not going to work with sampled blocks.")

    block_list = j['blockList']

    sys.stderr.write('Creating block range list.\n')
    block_ranges = load_block_ranges(block_list)

    sys.stderr.write('Clamping block contents.\n')
    clamp_block_contents(block_ranges, block_list)

    sys.stderr.write('Saving file.\n')

    # All of this temp file moving around and zipping stuff is
    # taken from memory/replace/dmd/dmd.py, in mozilla-central.
    tmpFile = tempfile.NamedTemporaryFile(delete=False)
    tmpFilename = tmpFile.name
    if isZipped:
        tmpFile = gzip.GzipFile(filename='', fileobj=tmpFile)

    json.dump(j, tmpFile, sort_keys=True)

    shutil.move(tmpFilename, input_file_name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments: need input file names.\n')
        exit()

    clamp_file_addresses(sys.argv[1])
