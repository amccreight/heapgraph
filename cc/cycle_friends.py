#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser


# Find the objects that are rooting a particular object (or objects of
# a certain class) in the cycle collector graph
#
# This works by reversing the graph, then flooding to find roots.
#
# There are various options to alter what is treated as a root, but
# these are mostly experimental, so they may not produce particularly
# useful results.
#
# --node-name-as-root nsRange (for example) will treat all objects
# with the node name nsRange as roots.  This is useful if a previous
# analysis has determined that a leak always involves an object being
# held onto by a certain class, and you want to continue with manual
# analysis starting at that object.



# Command line arguments

usage = "usage: %prog file_name target\n\
  file_name is the name of the cycle collector graph file\n\
  target is the object to look for"
parser = OptionParser(usage=usage)

options, args = parser.parse_args()

if len(args) != 2:
  print 'Expected two arguments.'
  exit(0)


def reverseGraph (g):
  g2 = {}
  print 'Reversing graph.'
  sys.stdout.flush()
  for src, dsts in g.iteritems():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  return g2


def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  #sys.stdout.write ('Converting to single graph. ') 
  #sys.stdout.flush()
  g = parse_cc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga, res)


def reachableFrom (g, garb, x):
  if not x in garb:
    print x, "is not garbage"
    exit -1

  visited = {x:True}
  working = [x]
  s = set([x])

  while [] != working:
    curr = working.pop()

    if not curr in g:
      continue

    for next in g[curr]:
      if not next in visited and next in garb:
        visited[next] = True
        working.append(next)
        s.add(next)

  return s


####################

file_name = args[0]
target = args[1]

(g, ga, res) = loadGraph (file_name)

print
print "Computing forward direction"

# garbage objects reachable from target
forw = reachableFrom(g, res[1], target)

print "Computing backwards direction"

# garbage objects that reach target
revg = reverseGraph(g)
backw = reachableFrom(revg, res[1], target)

# members of garbage cycle including target
print "Cycle members:", 
cyc = list(forw & backw)
cyc.sort()

for i in cyc:
  print i,
print



