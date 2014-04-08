#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple
import node_parse_cc_graph
from optparse import OptionParser


# print out classes of live objects

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


obj_patt = re.compile ('(JS Object \([^\)]+\)) \(global=[0-9a-fA-F]*\)')

#starts_with = set (['nsGenericElement (XUL)', 'nsGenericElement (xhtml)', 'nsGenericElement (XBL)', \
#                      'nsNodeInfo (XUL)', 'nsNodeInfo (xhtml)', 'nsNodeInfo (XBL)', \
#                      'nsXPCWrappedJS', 'JS Object', 'nsDocument', 'XPCWrappedNative'])

starts_with = set (['nsGenericElement (XUL)', \
                      'nsGenericElement (xhtml) span ', \
                      'nsGenericElement (xhtml) a ', \
                      'nsGenericElement (xhtml) input ', \
                      'nsGenericElement (XBL)', \
                      'nsNodeInfo (XUL)', 'nsNodeInfo (xhtml)', 'nsNodeInfo (XBL)', \
                      'nsXPCWrappedJS', 'JS Object', 'nsDocument', 'XPCWrappedNative'])

# Skip the merging by uncommenting the next line.
#starts_with = set([])


def canonize_label(l):
#  return l

#  lm = obj_patt.match(l)
#  if lm:
#    return lm.group(1)
  for s in starts_with:
    if l.startswith(s):
      return s
  return l


def analyze_live (nodes, ga, garb):
  nls = {}

  for n in nodes - garb:
    # skipped marked nodes, on the assumption that the CC is decent about avoiding them
    if n in ga.gcNodes and ga.gcNodes[n]:
      continue

    l = ga.nodeLabels[n]
    l = canonize_label(l)
    nls[l] = nls.get(l, 0) + 1

  other = 0
  for l, n in nls.iteritems():
    if n > 0:
      print '%(num)8d %(label)s' % {'num':n, 'label':l}
    else:
      other += n

  if other != 0:
    print '%(num)8d,other' % {'num':other}

def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga, res) = node_parse_cc_graph.parseCCEdgeFile(fname)
  print 'Done loading graph.'

  return (g, ga, res)


####################

file_name = args[0]

(g, ga, res) = loadGraph (file_name)
(ke, garb) = res

analyze_live(g, ga, garb)

