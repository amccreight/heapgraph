#!/usr/bin/python

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

def nullToNone(s):
  if s == '0x0':
    return None
  return s


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
      target = e.group(1)
      edgeLabel = e.group(2)

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
        currNode = nm.group(1)
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
        addNode(currNode, isRefCounted, nodeInfo, nm.group(3))
      elif l[:10] == '==========':
        break
      # Lines starting with '#' are comments, so ignore them.
      else:
        wmem = weakMapEntryPatt.match(l)
        if wmem:
          m = nullToNone(wmem.group(1))
          k = nullToNone(wmem.group(2))
          kd = nullToNone(wmem.group(3))
          v = nullToNone(wmem.group(4))
          assert(v != '0x0' and v != '(nil)')
          weakMapEntries.append((m, k, kd, v))
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
  print 'Warning!  Using experimental extension for parsing roots.  May be buggy.'
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


def printGraph(g):
  print 'Graph:'
  for x, edges in g.iteritems():
    sys.stdout.write('  {0}: '.format(x))
    for e, k in edges.iteritems():
      for n in range(k):
        sys.stdout.write('{0}, '.format(e))
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

  print 'Edge labels: ',
  for src, edges in ga.edgeLabels.iteritems():
    for dst, l in edges.iteritems():
      sys.stdout.write('{0}->{1}:{2}, '.format(src, dst, l))
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

# XXX This function isn't really right, as you only want to add these edges
# when you already know that, say, m and k are definitely alive.  I'm not sure
# how to go about doing that.
# Add the reversed edges induced by the weak map entries to the graph g.
# As a bit of a hack, if there's an entry with say map m, key k and value v
# (ignoring delegates for the moment) then in the reversed graph this sort of acts
# like there's an edge from v to m and an edge from v to k.  The standard flooding
# algorithm should produce sensical results from this reversed graph.  Each such reversed
# "weak" edge includes the name of the other node in the pair, if it is explicitly present.
def addReversedWeakEdges(g, ga):
  for (m, k, kd, v) in ga.weakMapEntries:
    assert(m or k or kd)
    assert(v)

    # If m and kd are alive, then k is alive.
    if m and k:
      g.setdefault(k, set([])).add(m)
      if kd:
        delegateName = 'key delegate ' + kd
      else:
        delegateName = 'black key delegate'
      ga.edgeLabels[m].setdefault(k, []).append('weak map along with ' + delegateName)

    if kd and k:
      g.setdefault(k, set([])).add(kd)
      if m:
        mapName = 'weak map ' + m
      else:
        mapName = 'black weak map'
      ga.edgeLabels[kd].setdefault(k, []).append('key delegate along with ' + mapName)

    # If m and k are alive, then v is alive.
    if m:
      g.setdefault(v, set([])).add(m)
      if k:
        keyName = 'key ' + k
      else:
        keyName = 'black key'
      ga.edgeLabels[m].setdefault(v, []).append('weak map along with ' + keyName)

    if k:
      g.setdefault(v, set([])).add(k)
      if m:
        mapName = 'weak map ' + m
      else:
        mapName = 'black weak map'
      ga.edgeLabels[k].setdefault(v, []).append('key along with ' + mapName)


if False:
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
