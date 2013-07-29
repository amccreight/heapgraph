#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple
import parse_cc_graph


def node_string (x, ga):
  if x in ga.rcNodes:
    t = 'rc=' + str(ga.rcNodes[x])
  elif ga.gcNodes[x]:
    t = 'gc.marked'
  else:
    t = 'gc'
  if x in ga.nodeLabels:
    lbl = ' ' + ga.nodeLabels[x]
  else:
    lbl = ''
  return '{0} [{1}]{2}'.format(x, t, lbl)


def edge_string (dst, olbl, lbl):
  t = '> ' + dst
  if olbl != None:
    t += ' {' + olbl + '}'
  if lbl != None:
    t += ' ' + lbl
  return t


def print_reverse_graph (g, ga):
  for src, outs in g.iteritems():
    print node_string(src, ga)
    for dst, numEdges in outs.iteritems():
      if (dst, src) in ga.edgeLabels:
        for ll in ga.edgeLabels[(dst, src)]:
          print edge_string (dst, ll[0], ll[1])
        numEdges -= len(ga.edgeLabels[(dst, src)])
      for x in range(numEdges):
        print edge_string (dst, None, None)

if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()


x = parse_cc_graph.parseCCEdgeFile(sys.argv[1])

r = parse_cc_graph.reverseMultigraph(x[0])
#assert(x[0] == parse_cc_graph.reverseMultigraph(r)

print_reverse_graph (r, x[1])




