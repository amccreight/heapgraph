#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Library for parsing garbage collector log files into a graph data structure.


import sys
import re
from collections import namedtuple



GraphAttribs = namedtuple('GraphAttribs', 'edgeLabels nodeLabels roots rootLabels weakMapEntries')
WeakMapEntry = namedtuple('WeakMapEntry', 'weakMap key keyDelegate value')

####
####  Log parsing
####

nodePatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
edgePatt = re.compile ('> ((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
weakMapEntryPatt = re.compile ('WeakMapEntry map=([a-zA-Z0-9]+|\(nil\)) key=([a-zA-Z0-9]+|\(nil\)) keyDelegate=([a-zA-Z0-9]+|\(nil\)) value=([a-zA-Z0-9]+)\r?$')

# A bit of a hack.  I imagine this could fail in bizarre circumstances.

def switchToGreyRoots(l):
  return l == "XPC global object" or l.startswith("XPCWrappedNative") or \
      l.startswith("XPCVariant") or l.startswith("nsXPCWrappedJS")

def parseRoots (f):
  roots = {}
  rootLabels = {}
  blackRoot = True;
  weakMapEntries = []

  for l in f:
    nm = nodePatt.match(l)
    if nm:
      addr = nm.group(1)
      color = nm.group(2)
      lbl = nm.group(3)

      if blackRoot and switchToGreyRoots(lbl):
        blackRoot = False

      # Don't overwrite an existing root, to avoid replacing a black root with a gray root.
      if not addr in roots:
        roots[addr] = blackRoot
        # It would be classier to save all the root labels, though then we have to worry about gray vs black.
        rootLabels[addr] = lbl
    else:
      wmm = weakMapEntryPatt.match(l)
      if wmm:
        weakMapEntries.append(WeakMapEntry(weakMap=wmm.group(1), key=wmm.group(2),
                                           keyDelegate=wmm.group(3), value=wmm.group(4)))
      elif l[:10] == '==========':
        break
      elif l[0] == '#':
        # Skip over comments.
        continue
      else:
        print "Error: unknown line ", l
        exit(-1)

  return [roots, rootLabels, weakMapEntries]


# parse CC graph
def parseGraph (f):
  edges = {}
  edgeLabels = {}
  nodeLabels = {}
  rcNodes = {}
  gcNodes = {}

  def addNode (node, nodeLabel):
    assert(not node in edges)
    edges[node] = {}
    assert(not node in edgeLabels)
    edgeLabels[node] = {}
    assert(nodeLabel != None)
    if nodeLabel != '':
      assert (not node in nodeLabels)
      nodeLabels[node] = nodeLabel

  def addEdge (source, target, edgeLabel):
    edges[source][target] = edges[source].get(target, 0) + 1
    if edgeLabel != '':
      edgeLabels[source].setdefault(target, []).append(edgeLabel)

  currNode = None

  for l in f:
    e = edgePatt.match(l)
    if e:
      assert(currNode != None)
      addEdge(currNode, e.group(1), e.group(3))
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = nm.group(1)
        nodeColor = nm.group(2)
        addNode(currNode, nm.group(3))
      elif l[0] == '#':
        # Skip over comments.
        continue
      else:
        print 'Error: Unknown line:', l[:-1]

  # yar, should pass the root crud in and wedge it in here, or somewhere
  return [edges, edgeLabels, nodeLabels]


def parseGCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  [roots, rootLabels, weakMapEntries] = parseRoots(f)
  [edges, edgeLabels, nodeLabels] = parseGraph(f)
  f.close()

  ga = GraphAttribs (edgeLabels=edgeLabels, nodeLabels=nodeLabels, roots=roots,
                     rootLabels=rootLabels, weakMapEntries=weakMapEntries)
  return (edges, ga)


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


def printGraph(g, ga):
  for x, edges in g.iteritems():
    if x in ga.roots:
      sys.stdout.write('R {0}: '.format(x))
    else:
      sys.stdout.write('  {0}: '.format(x))
    for e, k in edges.iteritems():
      for n in range(k):
        sys.stdout.write('{0}, '.format(e))
    print

def printAttribs(ga):
  print 'Roots: ',
  for x in ga.roots:
    sys.stdout.write('{0}, '.format(x))
  print
  return;

  print 'Node labels: ',
  for x, l in ga.nodeLabels.iteritems():
    sys.stdout.write('{0}:{1}, '.format(x, l))
  print

  print 'Edge labels: ',
  for src, edges in ga.edgeLabels.iteritems():
    for dst, l in edges.iteritems():
      sys.stdout.write('{0}->{1}:{2}, '.format(src, dst, l))
  print


if False:
  # A few simple tests

  if len(sys.argv) < 2:
    print 'Not enough arguments.'
    exit()

  #import cProfile
  #cProfile.run('x = parseGCEdgeFile(sys.argv[1])')

  x = parseGCEdgeFile(sys.argv[1])

  #printGraph(x[0], x[1])
  printAttribs(x[1])

  assert (x[0] == reverseMultigraph(reverseMultigraph(x[0])))
