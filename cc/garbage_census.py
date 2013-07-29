#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser


# print out classes of garbage objects

# Command line arguments

usage = "usage: %prog file_name\n\
  file_name is the name of the cycle collector graph file"
parser = OptionParser(usage=usage)

options, args = parser.parse_args()

if len(args) != 1:
  print 'Expected one argument.'
  exit(0)


# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))

def analyze_garbage (ga, garb):
  unknown = 0
  nls = {}

  for g in garb:
    if g in ga.nodeLabels:
      nls[ga.nodeLabels[g]] = nls.get(ga.nodeLabels[g], 0) + 1
    else:
      unknown += 1

  print

  if unknown != 0:
    print
    print "number of nodes lacking labels:", unknown
    print

  for l, n in nls.iteritems():
    print n, "\t", l


def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  g = parse_cc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga, res)


####################

file_name = args[0]

(g, ga, res) = loadGraph (file_name)
(ke, garb) = res
analyze_garbage(ga, garb)

