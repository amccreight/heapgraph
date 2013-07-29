#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Create a version of the CC log with the marked GC objects removed.
# Should we remove all references to that object, too?  That would be
# trickier and may require two passes.

import sys
import re
from collections import namedtuple


####
####  Log parsing
####

nodePatt = re.compile ('([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] ([^\r\n]*)\r?$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) ([^\r\n]*)\r?$')


def getMarkedNodes (f):
  # first, compute the set of marked JS nodes
  markedNodes = set([])

  for l in f:
    if l[0] == '>':
      continue
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = nm.group(1)
        nodeTy = nm.group(2)
        if nodeTy == 'gc.marked':
          markedNodes.add(currNode)
      elif l[:10] == '==========':
        break
      else:
        sys.stderr.write('Error: Unknown line:' + l[:-1])

  return markedNodes


def echoNonMarkedNodes (f, markedNodes):
  inMarked = False

  for l in f:
    if l[0] == '>':
      if not inMarked:
        e = edgePatt.match(l)
        assert(currNode != None)
        target = e.group(1)
        if not target in markedNodes:
          sys.stdout.write(l)
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = nm.group(1)
        nodeTy = nm.group(2)
        if nodeTy == 'gc.marked':
          inMarked = True
        else:
          inMarked = False
          sys.stdout.write(l)
      elif l[:10] == '==========':
        sys.stdout.write(l)
        break
      else:
        print 'Error: Unknown line:', l[:-1]
  


resultPatt = re.compile ('([a-zA-Z0-9]+) \[([a-z0-9=]+)\]\w*')
knownPatt = re.compile ('known=(\d+)')


def parseResults (f):
  garbage = set([])
  knownEdges = {}

  for l in f:
    rm = resultPatt.match(l)
    if rm:
      obj = rm.group(1)
      tag = rm.group(2)
      if tag == 'garbage':
        assert(not obj in garbage)
        garbage.add(obj)
      else:
        km = knownPatt.match(tag)
        if km:
          assert (not obj in knownEdges)
          knownEdges[obj] = int(km.group(1))
        else:
          print 'Error: Unknown result entry type:', tag
    else:
      print 'Error: Unknown result entry:', l[:-1]

  return (knownEdges, garbage)


def parseCCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  markedNodes = getMarkedNodes (f)
  f.close()

  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  echoNonMarkedNodes(f, markedNodes)

  f.close()


# Some applications may not care about multiple edges.
# They can instead use a single graph, which is represented as a map
# from a source node to a set of its destinations.
def toSinglegraph (gm):
  g = {}
  for src, dsts in gm.iteritems():
    d = set([])
    for dst, k in dsts.iteritems():
      d.add(dst)
    g[src] = d
  return g


def reverseMultigraph (gm):
  gm2 = {}
  for src, dsts in gm.iteritems():
    if not src in gm2:
      gm2[src] = {}
    for dst, k in dsts.iteritems():
      gm2.setdefault(dst, {})[src] = k
  return gm2


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseCCEdgeFile(sys.argv[1])



