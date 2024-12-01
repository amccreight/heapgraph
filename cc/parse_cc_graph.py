#!/usr/bin/python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Library for parsing cycle collector log files into a graph data structure.


# parseCCEdgeFile (file_name): given the file name of a CC edge file, parse and
#   return the data.  This function returns a tuple with two components.
#
#   The first component is a multigraph representing the nodes and
#   edges in the graph.  It is implemented as a dictionary of
#   dictionaries.  The domain of the outer dictionary is the nodes of
#   the graphs.  The inner dictionaries map the destinations of the
#   edges in the graph to the number of times they occur.  For
#   instance, if there are two edges from x to y in the multigraph g,
#   then g[x][y] == 2.
#
#   The second component contains various graph attributes in a GraphAttribs
#      - nodeLabels maps node names to their labels, if any
#      - rcNodes maps ref counted nodes to the number of references
#        they have
#      - gcNodes maps gc'd nodes to a boolean, which is True if the
#        node is marked, False otherwise.
#      - edgeLabels maps source nodes to dictionaries.  These inner
#        dictionaries map destination nodes to a list of edge labels.


# toSinglegraph (gm): convert a multigraph into a single graph

# reverseMultigraph (gm): reverse a multigraph

# printGraph(g): print out a graph

# printAttribs(ga): print out graph attributes


import sys
import re
from collections import namedtuple



GraphAttribs = namedtuple('GraphAttribs',
                          'edgeLabels nodeLabels rcNodes gcNodes xpcRoots purpRoots weakMapEntries incrRoots')
WeakMapEntry = namedtuple('WeakMapEntry', 'weakMap key keyDelegate value')


# experimental support for parsing purple roots
fileHasCounts = False


####
####  Log parsing
####

nodePatt = re.compile ('([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] ([^\r\n]*)\r?$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) ([^\r\n]*)\r?$')
weakMapEntryPatt = re.compile ('WeakMapEntry map=([a-zA-Z0-9]+|\(nil\)) key=([a-zA-Z0-9]+|\(nil\)) keyDelegate=([a-zA-Z0-9]+|\(nil\)) value=([a-zA-Z0-9]+)\r?$')
incrRootPatt = re.compile('IncrementalRoot ([a-zA-Z0-9]+)\r?$')


checkForDoubleLogging = True


# parse CC graph
def parseGraph (f, rootCounts):
  edges = {}
  edgeLabels = {}
  nodeLabels = {}
  rcNodes = {}
  gcNodes = {}
  weakMapEntries = []
  incrRoots = set([])

  xpcRoots = set([])
  purpRoots = set([])
  numNodes = 0

  nodeInternmentTable = {}
  edgeInternmentTable = {}

  def uniquify(table, label):
    if label in table:
      return table[label];
    table[label] = label
    return label

  def addNode (node, isRefCounted, nodeInfo, nodeLabel):
    if checkForDoubleLogging:
      assert(not node in edges)
    edges[node] = {}
    if checkForDoubleLogging:
      assert(not node in edgeLabels)
    edgeLabels[node] = {}
    if isRefCounted:
      if checkForDoubleLogging:
        assert (not node in rcNodes)
      rcNodes[node] = nodeInfo
    else:
      assert (not node in gcNodes)
      gcNodes[node] = nodeInfo
    assert(nodeLabel != None)
    if nodeLabel != '':
      if checkForDoubleLogging:
        assert (not node in nodeLabels)
      nodeLabels[node] = nodeLabel

  currNode = None

  for l in f:
#    e = edgePatt.match(l)
#    if e:
    if l[0] == '>':
      e = edgePatt.match(l)
      assert(currNode != None)
      target = int(e.group(1), 16)
      edgeLabel = uniquify(edgeInternmentTable, e.group(2))

#    if l[0] == '>':
#      edge_addr_end = l.index(' ', 2)
#      target = l[2:edge_addr_end]
#      edgeLabel = l[edge_addr_end+1:]

      edges[currNode][target] = edges[currNode].get(target, 0) + 1
      if edgeLabel != '':
        edgeLabels[currNode].setdefault(target, []).append(edgeLabel)
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = int(nm.group(1), 16)
        numNodes += 1
        if fileHasCounts:
          if numNodes <= rootCounts[0]:
            xpcRoots.add(currNode)
          elif numNodes <= rootCounts[1]:
            purpRoots.add(currNode)
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
        addNode(currNode, isRefCounted, nodeInfo, uniquify(nodeInternmentTable, nm.group(3)))
      elif l[:10] == '==========':
        break
      # Lines starting with '#' are comments, so ignore them.
      else:
        wmem = weakMapEntryPatt.match(l)
        if wmem:
          weakMapEntries.append(WeakMapEntry(weakMap=wmem.group(1), key=wmem.group(2),
                                             keyDelegate=wmem.group(3), value=wmem.group(4)))
        else:
          iroot = incrRootPatt.match(l)
          if iroot:
            incrRoots.add(iroot.group(1))
          elif l[0] != '#':
            sys.stderr.write('Error: skipping unknown line:' + l[:-1] + '\n')

  ga = GraphAttribs (edgeLabels=edgeLabels, nodeLabels=nodeLabels,
                     rcNodes=rcNodes, gcNodes=gcNodes,
                     xpcRoots=xpcRoots, purpRoots=purpRoots,
                     weakMapEntries=weakMapEntries, incrRoots=incrRoots)

  return (edges, ga)


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
          # For some reason 0x0 is in the results sometimes.
          assert (not obj in knownEdges or obj == '0x0')
          knownEdges[obj] = int(km.group(1))
        else:
          sys.stderr.write('Error: Unknown result entry type:' + tag + '\n')
    else:
      sys.stderr.write('Error: Unknown result entry:' + l[:-1] + '\n')

  return (knownEdges, garbage)




# parsing of root counts

countPatt = re.compile ('0x0 \[rc=([0-9]+)\] COUNT_ROOTS\r?$')

def parseCounts(f):
  print('Warning!  Using experimental extension for parsing roots.  May be buggy.')
  l = f.readline()
  cpm = countPatt.match(l)
  assert(cpm)
  xpcCount = int(cpm.group(1))
  l = f.readline()
  cpm = countPatt.match(l)
  assert(cpm)
  purpleCount = int(cpm.group(1))
  return (xpcCount, purpleCount)

def parseCCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    sys.stderr.write('Error opening file ' + fname + '\n')
    exit(-1)

  if fileHasCounts:
    rootCounts = parseCounts(f)
  else:
    rootCounts = [0, 0]
  pg = parseGraph(f, rootCounts)
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


def printGraph(g):
  print('Graph:')
  for x, edges in g.items():
    sys.stdout.write('  {0}: '.format(x))
    for e, k in edges.items():
      for n in range(k):
        sys.stdout.write('{0}, '.format(e))
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

  print('Edge labels: ', end=' ')
  for src, edges in ga.edgeLabels.items():
    for dst, l in edges.items():
      sys.stdout.write('{0}->{1}:{2}, '.format(src, dst, l))
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


if __name__ == "__main__":
  # A few simple tests

  if len(sys.argv) < 2:
    sys.stderr.write('Not enough arguments.\n')
    exit()

  #import cProfile
  #cProfile.run('x = parseCCEdgeFile(sys.argv[1])')

  x = parseCCEdgeFile(sys.argv[1])

  exit(0)

  printGraph(x[0])
  printAttribs(x[1])
  printResults(x[2])

  assert (x[0] == reverseMultigraph(reverseMultigraph(x[0])))
