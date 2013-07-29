#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# variant of the parser library that skips over edges


import sys
import re
from collections import namedtuple



GraphAttribs = namedtuple('GraphAttribs', 'nodeLabels rcNodes gcNodes')


####
####  Log parsing
####

nodePatt = re.compile ('([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] (.*)$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) (.*)$')


# parse CC graph
def parseGraph (f):
  nodes = set([])
  nodeLabels = {}
  rcNodes = {}
  gcNodes = {}

  def addNode (node, isRefCounted, nodeInfo, nodeLabel):
    # commented out due to bug in Node logging
    # assert(not node in nodes)
    nodes.add(node)
    if isRefCounted:
      # commented out due to bug in Node logging
      # assert (not node in rcNodes)
      rcNodes[node] = nodeInfo
    else:
      assert (not node in gcNodes)
      gcNodes[node] = nodeInfo
    assert(nodeLabel != None)
    if nodeLabel != '':
      # commented out due to bug in Node logging
      # assert (not node in nodeLabels)
      nodeLabels[node] = nodeLabel

  currNode = None

  for l in f:
    if l[0] == '>':
      continue

    nm = nodePatt.match(l)
    if nm:
      currNode = nm.group(1)
      nodeTy = nm.group(2)
      if nodeTy == 'gc':
        isRefCounted = False
        nodeInfo = False
      elif nodeTy == 'gc.marked':
        isRefCounted = False
        nodeInfo = True
      else:
        isRefCounted = True
        nodeInfo = int(nodeTy[3:])
      addNode(currNode, isRefCounted, nodeInfo, nm.group(3))
    elif l.startswith('=========='):
      break
    elif not l.startswith('#'):
      print 'Error: Unknown line:', l[:-1]

  ga = GraphAttribs (nodeLabels=nodeLabels,
                     rcNodes=rcNodes, gcNodes=gcNodes)
  return (nodes, ga)


resultPatt = re.compile ('([a-zA-Z0-9]+) \[([a-z0-9=]+)\]$')
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
          break
    else:
      print 'Error: Unknown result entry:', l[:-1]
      break

  return (knownEdges, garbage)


def parseCCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  pg = parseGraph(f)
  pr = parseResults(f)
  f.close()
  return (pg[0], pg[1], pr)


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


def printGraph(nodes):
  print 'Graph:'
  for x in nodes:
    sys.stdout.write('  {0}: '.format(x))
    print

def printAttribs(ga):
  print 'RC nodes: ',
  for x, rc in ga.rcNodes.iteritems():
    sys.stdout.write('{0}={1}, '.format(x, rc))
  print

  print 'Marked GC nodes: ',
  for x, marked in ga.gcNodes.iteritems():
    if marked:
      sys.stdout.write('{0}, '.format(x))
  print

  print 'Unmarked GC nodes: ',
  for x, marked in ga.gcNodes.iteritems():
    if not marked:
      sys.stdout.write('{0}, '.format(x))
  print

  print 'Node labels: ',
  for x, l in ga.nodeLabels.iteritems():
    sys.stdout.write('{0}:{1}, '.format(x, l))
  print

def printResults(r):
  print 'Known edges: ',
  for x, k in r[0].iteritems():
    sys.stdout.write('{0}={1}, '.format(x, k))
  print

  print 'Garbage: ',
  for x in r[1]:
    sys.stdout.write('{0}, '.format(x))
  print



if False:
  # A few simple tests

  if len(sys.argv) < 2:
    print 'Not enough arguments.'
    exit()

  #import cProfile
  #cProfile.run('x = parseCCEdgeFile(sys.argv[1])')

  x = parseCCEdgeFile(sys.argv[1])

  printGraph(x[0])
  printAttribs(x[1])
  printResults(x[2])

  assert (x[0] == reverseMultigraph(reverseMultigraph(x[0])))
