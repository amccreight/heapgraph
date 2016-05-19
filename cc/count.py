#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import parse_cc_graph
import argparse

parser = argparse.ArgumentParser(description='')

parser.add_argument('file_name',
                    help='graph file name')

def countNodeLabels ():
  args = parser.parse_args()
  (g, ga, foo) = parse_cc_graph.parseCCEdgeFile(args.file_name)

  # Count up unique node labels
  nodes = {}
  for x, l in ga.nodeLabels.iteritems():
    if not l in nodes:
      nodes[l] = 0
    nodes[l] = nodes[l] + 1

  # Sort by count
  results = []
  for n, c in nodes.iteritems():
    results.append((c, n))
  results.sort(key=lambda tup: tup[0])

  # Output
  for r in results:
    print '{0} {1}'.format(r[0], r[1])

if __name__ == "__main__":
  countNodeLabels()
