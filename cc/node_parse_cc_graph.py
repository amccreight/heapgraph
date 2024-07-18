#!/usr/bin/python3

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

nodePatt = re.compile(r'([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] (.*)$')
edgePatt = re.compile(r'> ([a-zA-Z0-9]+) (.*)$')
weakMapEntryPatt = re.compile(r'WeakMapEntry map=([a-zA-Z0-9]+|\(nil\)) key=([a-zA-Z0-9]+|\(nil\)) keyDelegate=([a-zA-Z0-9]+|\(nil\)) value=([a-zA-Z0-9]+)\r?$')
incrRootPatt = re.compile(r'IncrementalRoot ([a-zA-Z0-9]+)\r?$')


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
    elif l.startswith('#'):
      # skip comments
      continue
    else:
      if weakMapEntryPatt.match(l):
        # ignore weak map entries
        continue
      elif incrRootPatt.match(l):
        # ignore incremental root entries
        continue
      else:
        sys.stderr.write('Error: skipping unknown line:' + l[:-1] + '\n')

  ga = GraphAttribs (nodeLabels=nodeLabels,
                     rcNodes=rcNodes, gcNodes=gcNodes)
  return (nodes, ga)


resultPatt = re.compile(r'([a-zA-Z0-9]+) \[([a-z0-9=]+)\]$')
knownPatt = re.compile(r'known=(\d+)')


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
          sys.stderr.write('Error: Unknown result entry type: ' + tag + '\n')
          break
    else:
      sys.stderr.write('Error: Unknown result entry: ' + l[:-1] + '\n')
      break

  return (knownEdges, garbage)


def parseCCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    sys.stderr.write('Error opening file ' + fname + '\n')
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
  for src, dsts in gm.items():
    d = set([])
    for dst, k in dsts.items():
      d.add(dst)
    g[src] = d
  return g


def reverseMultigraph (gm):
  gm2 = {}
  for src, dsts in gm.items():
    if not src in gm2:
      gm2[src] = {}
    for dst, k in dsts.items():
      gm2.setdefault(dst, {})[src] = k
  return gm2


def printGraph(nodes):
  print('Graph:')
  for x in nodes:
    sys.stdout.write('  {0}: '.format(x))
    print()

def printAttribs(ga):
  print('RC nodes: ', end=' ')
  for x, rc in ga.rcNodes.items():
    sys.stdout.write('{0}={1}, '.format(x, rc))
  print()

  print('Marked GC nodes: ', end=' ')
  for x, marked in ga.gcNodes.items():
    if marked:
      sys.stdout.write('{0}, '.format(x))
  print()

  print('Unmarked GC nodes: ', end=' ')
  for x, marked in ga.gcNodes.items():
    if not marked:
      sys.stdout.write('{0}, '.format(x))
  print()

  print('Node labels: ', end=' ')
  for x, l in ga.nodeLabels.items():
    sys.stdout.write('{0}:{1}, '.format(x, l))
  print()

def printResults(r):
  print('Known edges: ', end=' ')
  for x, k in r[0].items():
    sys.stdout.write('{0}={1}, '.format(x, k))
  print()

  print('Garbage: ', end=' ')
  for x in r[1]:
    sys.stdout.write('{0}, '.format(x))
  print()



if False:
  # A few simple tests

  if len(sys.argv) < 2:
    sys.stderr.write('Not enough arguments.\n')
    exit()

  #import cProfile
  #cProfile.run('x = parseCCEdgeFile(sys.argv[1])')

  x = parseCCEdgeFile(sys.argv[1])

  printGraph(x[0])
  printAttribs(x[1])
  printResults(x[2])

  assert (x[0] == reverseMultigraph(reverseMultigraph(x[0])))
