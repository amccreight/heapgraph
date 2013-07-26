#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple
import parse_gc_graph
import argparse


# get an overview of what is in the heap

# Command line arguments

parser = argparse.ArgumentParser(description='Overview of what is in the GC heap.')

parser.add_argument('file_name',
                    help='cycle collector graph file name')

args = parser.parse_args()


def loadGraph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  sys.stderr.flush()
  (g, ga) = parse_gc_graph.parseGCEdgeFile(fname)
  g = parse_gc_graph.toSinglegraph(g)
  sys.stderr.write('Done loading graph.')

  return (g, ga)


####################

addrPatt = re.compile ('(?:0x)?[a-fA-F0-9]+')


(g, ga) = loadGraph (args.file_name)

counter = {}

for src, dst in ga.nodeLabels.iteritems():
  counter[dst] = counter.get(dst, 0) + 1

for name, count in counter.iteritems():
  print '%(num)8d %(label)s' % {'num':count, 'label':name}






