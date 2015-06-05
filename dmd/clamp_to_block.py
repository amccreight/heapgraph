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


def loadBlockRanges(blockList):
    ranges = []

    for block in blockList:
        ranges.append(AddrRange(block['addr'], block['req']))

    ranges.sort(key=lambda r: r.start)

    # Make sure there are no overlapping blocks.
    newRanges = []
    lastOverlapped = False

    for currRange in ranges:
        if len(newRanges) == 0:
            newRanges.append(currRange)
            continue

        prevRange = newRanges[-1]
        assert prevRange.start < currRange.start

        if currRange.start < prevRange.end():
            lastOverlapped = True
            # Keep the block at the end that ends the latest.
            if prevRange.end() < currRange.end():
                newRanges[-1] = currRange
        else:
            if lastOverlapped:
                newRanges[-1] = currRange
            else:
                newRanges.append(currRange)
            lastOverlapped = False

    if lastOverlapped:
        newRanges.pop()
        lastOverlapped = False

    assert len(ranges) == len(newRanges) # Shouldn't have any overlapping blocks.

    return newRanges


# Search the block ranges array for a block that address points into.
# Address is an address as a hex string.
def getClampedAddress(blockRanges, address):
    address = int(address, 16)

    low = 0
    high = len(blockRanges) - 1
    while low <= high:
        mid = low + (high - low) / 2
        if address < blockRanges[mid].start:
            high = mid - 1
            continue
        if address >= blockRanges[mid].end():
            low = mid + 1
            continue
        return blockRanges[mid].block

    return None


class ClampStats:
    def __init__(self):
        # Already pointing to the start of a block.
        self.startBlockPtr = 0

        # Pointing to the middle of a block, clamped to start.
        self.midBlockPtr = 0

        # Number of null pointers found.
        self.nullPtr = 0

        # Number of non-null pointers found that didn't point to
        # blocks.
        self.nonNullNonBlockPtr = 0


    def clampedBlockAddr(self, sameAddress):
        if sameAddress:
            self.startBlockPtr += 1
        else:
            self.midBlockPtr += 1

    def clampedNonBlockAddr(self, sameAddress):
        if sameAddress:
            self.nullPtr += 1
        else:
            self.nonNullNonBlockPtr += 1

    def log(self):
        sys.stderr.write('Results:\n')
        sys.stderr.write('  Number of pointers already pointing to start of blocks: ' + str(self.startBlockPtr) + '\n')
        sys.stderr.write('  Number of pointers clamped to start of blocks: ' + str(self.midBlockPtr) + '\n')
        sys.stderr.write('  Number of non-null pointers not pointing into blocks: ' + str(self.nonNullNonBlockPtr) + '\n')
        sys.stderr.write('  Number of null pointers: ' + str(self.nullPtr) + '\n')


def clampAddress(blockRanges, clampStats, address):
    clamped = getClampedAddress(blockRanges, address)
    if clamped:
        clampStats.clampedBlockAddr(address == clamped)
        return clamped
    else:
        clampStats.clampedNonBlockAddr(address == '0')
        return '0'


def clampBlockContents(blockRanges, blockList):
    clampStats = ClampStats()

    for block in blockList:
        # Small blocks don't have any contents.
        if not 'contents' in block:
            continue

        newContents = []
        for address in block['contents']:
            newContents.append(clampAddress(blockRanges, clampStats, address))

        block['contents'] = newContents

    clampStats.log()


def clampFileAddresses(inputFileName):
    sys.stderr.write('Loading file.\n')
    isZipped = inputFileName.endswith('.gz')
    opener = gzip.open if isZipped else open

    with opener(inputFileName, 'rb') as f:
        j = json.load(f)

    if j['version'] != outputVersion:
        raise Exception("'version' property isn't '{:d}'".format(outputVersion))

    invocation = j['invocation']
    sampleBelowSize = invocation['sampleBelowSize']
    heapIsSampled = sampleBelowSize > 1
    if heapIsSampled:
        raise Exception("Heap analysis is not going to work with sampled blocks.")

    if invocation['mode'] != 'contents':
        raise Exception("Log was taken in mode " + invocation['mode'] + " not contents")

    blockList = j['blockList']

    sys.stderr.write('Creating block range list.\n')
    blockRanges = loadBlockRanges(blockList)

    sys.stderr.write('Clamping block contents.\n')
    clampBlockContents(blockRanges, blockList)

    sys.stderr.write('Saving file.\n')

    # All of this temp file moving around and zipping stuff is
    # taken from memory/replace/dmd/dmd.py, in mozilla-central.
    tmpFile = tempfile.NamedTemporaryFile(delete=False)
    tmpFilename = tmpFile.name
    if isZipped:
        tmpFile = gzip.GzipFile(filename='', fileobj=tmpFile)

    json.dump(j, tmpFile, sort_keys=True)

    shutil.move(tmpFilename, inputFileName)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments: need input file names.\n')
        exit()

    clampFileAddresses(sys.argv[1])
