#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import collections
import parse_cc_graph


parser = argparse.ArgumentParser(description='Find objects with more references than their refcount')

parser.add_argument('file_name',
                    help='cycle collector graph file name')

args = parser.parse_args()
(g, ga, res) = parse_cc_graph.parseCCEdgeFile(args.file_name)


knownReferences = collections.defaultdict(lambda: 0)
for x, edges in g.iteritems():
    if not x in ga.rcNodes:
        continue
    for y, count in edges.iteritems():
        knownReferences[y] += count


for x in g.keys():
    if not x in ga.rcNodes:
        continue
    if knownReferences[x] > ga.rcNodes[x]:
        print 'Bad node {0} found (rc={1}, known={2})'.format(x, ga.rcNodes[x], knownReferences[x])
        exit(-1)



