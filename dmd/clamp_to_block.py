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
from bisect import bisect_right


# The DMD output version this script handles.
outputVersion = 4


# Start is the address of the first byte of the block, while end is
# the first byte past the end of the block.
class AddrRange:
    def __init__(self, block, length):
        self.block = block
        self.start = int(block, 16)
        self.length = length
        self.end = self.start + self.length

        assert self.start > 0
        assert length >= 0


class ClampStats:
    def __init__(self):
        # Number of pointers already pointing to the start of a block.
        self.startBlockPtr = 0

        # Number of pointers pointing to the middle of a block. These
        # are clamped to the start of the block they point into.
        self.midBlockPtr = 0

        # Number of null pointers.
        self.nullPtr = 0

        # Number of non-null pointers that didn't point into the middle
        # of any blocks. These are clamped to null.
        self.nonNullNonBlockPtr = 0


    def clampedBlockAddr(self, sameAddress):
        if sameAddress:
            self.startBlockPtr += 1
        else:
            self.midBlockPtr += 1

    def nullAddr(self):
        self.nullPtr += 1

    def clampedNonBlockAddr(self):
        self.nonNullNonBlockPtr += 1

    def log(self):
        sys.stderr.write('Results:\n')
        sys.stderr.write('  Number of pointers already pointing to start of blocks: ' + str(self.startBlockPtr) + '\n')
        sys.stderr.write('  Number of pointers clamped to start of blocks: ' + str(self.midBlockPtr) + '\n')
        sys.stderr.write('  Number of non-null pointers not pointing into blocks clamped to null: ' + str(self.nonNullNonBlockPtr) + '\n')
        sys.stderr.write('  Number of null pointers: ' + str(self.nullPtr) + '\n')


# Search the block ranges array for a block that address points into.
# The search is carried out in an array of starting addresses for each blocks
# because it is faster.
def clampAddress(blockRanges, blockStarts, clampStats, address):
    i = bisect_right(blockStarts, address)

    # Any addresses completely out of the range should have been eliminated already.
    assert i > 0
    r = blockRanges[i - 1]
    assert r.start <= address

    if address >= r.end:
        assert address < blockRanges[i].start
        clampStats.clampedNonBlockAddr()
        return '0'

    clampStats.clampedBlockAddr(r.start == address)
    return r.block


def clampBlockList(j):
    # Check that the invocation is reasonable for contents clamping.
    invocation = j['invocation']
    if invocation['sampleBelowSize'] > 1:
        raise Exception("Heap analysis is not going to work with sampled blocks.")
    if invocation['mode'] != 'scan':
        raise Exception("Log was taken in mode " + invocation['mode'] + " not scan")

    sys.stderr.write('Creating block range list.\n')
    blockList = j['blockList']
    blockRanges = []
    for block in blockList:
        blockRanges.append(AddrRange(block['addr'], block['req']))
    blockRanges.sort(key=lambda r: r.start)

    # Make sure there are no overlapping blocks.
    prevRange = blockRanges[0]
    for currRange in blockRanges[1:]:
        assert prevRange.end <= currRange.start
        prevRange = currRange

    sys.stderr.write('Clamping block contents.\n')
    clampStats = ClampStats()
    firstAddr = blockRanges[0].start
    lastAddr = blockRanges[-1].end

    blockStarts = []
    for r in blockRanges:
        blockStarts.append(r.start)

    for block in blockList:
        # Small blocks don't have any contents.
        if not 'contents' in block:
            continue

        cont = block['contents']
        for i in range(len(cont)):
            strAddress = cont[i]

            if strAddress == '0':
                clampStats.nullAddr()
                continue

            address = int(strAddress, 16)

            # If the address is before the first block or after the last
            # block then it can't be within a block.
            if address < firstAddr or address >= lastAddr:
                clampStats.clampedNonBlockAddr()
                cont[i] = '0'
                continue

            cont[i] = clampAddress(blockRanges, blockStarts, clampStats, address)

        # Remove any trailing nulls.
        while len(cont) and cont[-1] == '0':
            cont.pop()

    clampStats.log()


def alternateLoading(inputFileName):
    sys.stderr.write('Loading file.\n')
    isZipped = inputFileName.endswith('.gz')
    opener = gzip.open if isZipped else open

    # Should probably validate the header stuff...
    inHeader = True
    header = []
    inFooter = False
    footer = []
    blockList = []
    with opener(inputFileName, 'rb') as inputFile:
        for line in inputFile:
            if inHeader:
                header.append(line)
                if line == " \"blockList\": [\n":
                    inHeader = False
            elif inFooter:
                footer.append(line)
            elif line == " ],\n":
                footer.append(line)
                inFooter = True
            else:
                blockList.append(json.loads(line.rstrip('\n,')))

    fakeJson = {}
    fakeJson['invocation'] = {'sampleBelowSize':1, 'mode':'scan'}
    fakeJson['blockList'] = blockList
    clampBlockList(fakeJson)

    def writeBlock(tmpFile, b):
        tmpFile.write('  ')
        json.dump(b, tmpFile, sort_keys=True)

    # All of this temp file moving around and zipping stuff is
    # taken from memory/replace/dmd/dmd.py, in mozilla-central.
    sys.stderr.write('Saving file.\n')
    tmpFile = tempfile.NamedTemporaryFile(delete=False)
    tmpFilename = tmpFile.name
    if isZipped:
        tmpFile = gzip.GzipFile(filename='', fileobj=tmpFile)
    for l in header:
        tmpFile.write(l)
    writeBlock(tmpFile, blockList[0])
    for b in blockList[1:]:
        tmpFile.write(',\n')
        writeBlock(tmpFile, b)
    tmpFile.write('\n')
    for l in footer:
        tmpFile.write(l)
    shutil.move(tmpFilename, inputFileName)


def clampFileAddresses(inputFileName):
    sys.stderr.write('Loading file.\n')
    isZipped = inputFileName.endswith('.gz')
    opener = gzip.open if isZipped else open

    with opener(inputFileName, 'rb') as f:
        j = json.load(f)

    if j['version'] != outputVersion:
        raise Exception("'version' property isn't '{:d}'".format(outputVersion))

    clampBlockList(j)

    # All of this temp file moving around and zipping stuff is
    # taken from memory/replace/dmd/dmd.py, in mozilla-central.
    sys.stderr.write('Saving file.\n')
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

    alternateLoading(sys.argv[1])
    #clampFileAddresses(sys.argv[1])
