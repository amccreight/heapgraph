#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Extract arena information from a GC log.

import sys
import re


rootPatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (.*)$')

zonePatt = re.compile ('# zone (0x[a-fA-F0-9]+)$')
compPatt = re.compile ('# compartment (.+) \[in zone ((?:0x)?[a-fA-F0-9]+)\]$')
arenaPatt = re.compile ('# arena allockind=(\d+) size=(\d+)')

nodePatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
edgePatt = re.compile ('> ((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')



# This function takes a GC edges file and returns a list of zone descriptions.
#
# Each zone description is a triple.  The first element of the triple is the address of the zone.
# The second element of the triple is a list of compartment names. The third is a list of
# arena descriptions.
#
# Each arena description is a triple. The first element of the arena triple is the allockind.
# The second is the size in bytes of each thing in the arena. The third element is the number of
# allocated objects in the arena.
def parseZones(f):

    # First, skip past all the roots, which we don't care about.
    for l in f:
        nm = rootPatt.match(l)
        if not nm:
            if l == "==========\n":
                break;
            else:
                print "Error: unknown line ", l
                f.close()
                exit(-1)

    # Now read in all of the zones.
    zones = []
    currZone = None
    currArena = None

    for l in f:
        zm = zonePatt.match(l)
        if zm:
            if currArena:
                assert currZone
                currZone[2].append(currArena)
                currArena = None
            if currZone:
                zones.append(currZone)
            currZone = [zm.group(1), [], []]
            continue

        cm = compPatt.match(l)
        if cm:
            assert currZone
            assert not currArena

            z = cm.group(2)
            assert z == currZone[0]
            currZone[1].append(cm.group(1))
            continue

        am = arenaPatt.match(l)
        if am:
            assert currZone
            if currArena:
                currZone[2].append(currArena)

            currArena = [int(am.group(1)), int(am.group(2)), 0]
            continue
        nm = nodePatt.match(l)
        if nm:
            assert currZone
            assert currArena
            currArena[2] += 1
            continue
        em = edgePatt.match(l)
        if em:
            assert currZone
            assert currArena
            continue
        print 'Error: unknown line:', l[:-1]
        exit(-1)

    if currArena:
        currZone[2].append(currArena)
    if currZone:
        zones.append(currZone)

    return zones


def parseArenaFile(fname):
    try:
        f = open(fname, 'r')
    except:
        print 'Error opening file', fname
        exit(-1)

    zones = parseZones(f)

    f.close()

    return zones


# I think this is right?
arenaSize = 4096


def analyzeArena(a, out):
    allocKind = a[0]
    thingSize = a[1]
    numThings = a[2]

    usedSize = thingSize * numThings
    arenaSlop = thingSize % usedSize
    unusedSpace = arenaSize - usedSize

    unusedPerc = (100 * unusedSpace / arenaSize) / 5 * 5

    out[unusedPerc] += 1

    #out.append([100 * unusedSpace / arenaSize, 100 * arenaSlop / arenaSize, 100 * usedSize / arenaSize])

def doStuff():
    zones = parseArenaFile('gc-edges.310.log')

    print 'Number of arenas in each zone with a given percentage of unused space, crudely bucketed.'

    # Do some kind of analysis on the zones.
    for z in zones:
        print 'zone:', z[0]
        #print 'comp:', z[1]

        out = []
        i = 0
        while i <= 100:
            out.append(0)
            i += 1

        for a in z[2]:
            analyzeArena(a, out)

        i = 100
        while i >= 0:
            if out[i] > 0:
                sys.stdout.write('{0}%: {1}, '.format(i, out[i]))
            i -= 1
        print


doStuff()
