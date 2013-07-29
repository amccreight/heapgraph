#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple
import parse_cc_graph
import fast_parse_cc_graph


# which classes (or maybe even specific objects) hold into a particular class of objects?


# print out classes of live objects

# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))


obj_patt = re.compile ('(JS Object \([^\)]+\)) \(global=[0-9a-fA-F]*\)')



def canonicalize_name (n):
  nm = obj_patt.match(n)
  if nm:
    return nm.group(1)
  return n


def get_holders (g, ga, garb, name):
  children = set([])

  for n in g:
    if name == ga.nodeLabels[n]:
      children.add(n)

  print 'Num children found:', len(children)

  parents = {}

  for n, e in g.iteritems():
    overlap = e & children
    if len(overlap) != 0:
      l = canonicalize_name(ga.nodeLabels[n])
      parents[l] = parents.get(l, 0) + len(overlap)

  other = 0
  for l, n in parents.iteritems():
    if n > 0:
      print '%(num)8d %(label)s' % {'num':n, 'label':l}
    else:
      other += n

  if other != 0:
    print '%(num)8d other' % {'num':other}


def loadGraph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  sys.stderr.flush()
  (g, ga, res) = fast_parse_cc_graph.parseCCEdgeFile(fname)
  sys.stderr.write('Done loading graph.\n')
  sys.stderr.flush()

  return (g, ga, res)


####################

file_name = sys.argv[1]
class_name = sys.argv[2]

(g, ga, res) = loadGraph (file_name)
(ke, garb) = res
get_holders(parse_cc_graph.toSinglegraph(g), ga, garb, class_name)

