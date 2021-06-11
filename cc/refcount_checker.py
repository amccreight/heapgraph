#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re

# Very simple analyzer to check for refcounted objects with more references
# to them than their refcount.

fname = sys.argv[1]
try:
    f = open(fname, 'r')
except:
    sys.stderr.write('Error opening file ' + fname + '\n')
    exit(-1)


nodePatt = re.compile ('([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] ([^\r\n]*)\r?$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) ([^\r\n]*)\r?$')

g = {}
rcs = {}
referents = {}

currNode = None

for l in f:
    if l[0] == '#':
        continue
    if l[0] == '=':
        continue
    if l.startswith('WeakMapEntry'):
        continue
    if l[0] == '>':
        e = edgePatt.match(l)
        assert currNode != None
        target = e.group(1)
        g[currNode].append(target)
        referents[target] = referents.get(target, 0) + 1
        continue

    nm = nodePatt.match(l)
    assert nm
    currNode = nm.group(1)
    assert not currNode in g
    g[currNode] = []

    nodeTy = nm.group(2)
    if nodeTy != 'gc' and nodeTy != 'gc.marked':
        rc = int(nodeTy[3:])
        assert not currNode in rcs
        rcs[currNode] = rc

for x in rcs:
    if rcs[x] < referents.get(x, 0):
        print("Object %s has refcount %d but saw %d references to it" % (x, rcs[x], referents[x]))

f.close()
