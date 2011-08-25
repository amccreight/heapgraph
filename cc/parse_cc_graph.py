#!/usr/bin/python

# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# The Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****


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

# pringAttribs(ga): print out graph attributes


import sys
import re
from collections import namedtuple



GraphAttribs = namedtuple('GraphAttribs', 'edgeLabels nodeLabels rcNodes gcNodes')


####
####  Log parsing
####

nodePatt = re.compile ('([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] (.*)$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) (.*)$')


# parse CC graph
def parseGraph (f):
  edges = {}
  edgeLabels = {}
  nodeLabels = {}
  rcNodes = {}
  gcNodes = {}

  def addNode (node, isRefCounted, nodeInfo, nodeLabel):
    assert(not node in edges)
    edges[node] = {}
    assert(not node in edgeLabels)
    edgeLabels[node] = {}
    if isRefCounted:
      assert (not node in rcNodes)
      rcNodes[node] = nodeInfo
    else:
      assert (not node in gcNodes)
      gcNodes[node] = nodeInfo
    assert(nodeLabel != None)
    if nodeLabel != '':
      assert (not node in nodeLabels)
      nodeLabels[node] = nodeLabel

  def addEdge (source, target, edgeLabel):
    def addEdgeLabel (lbl):
      # this line is about 1/4 of the running time of the parser
      edgeLabels[source].setdefault(target, []).append(lbl)

    edges[source][target] = edges[source].get(target, 0) + 1

    if edgeLabel != '':
      addEdgeLabel(edgeLabel)

  currNode = None

  for l in f:
    e = edgePatt.match(l)
    if e:
      assert(currNode != None)
      addEdge(currNode, e.group(1), e.group(2))
    else:
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
      elif l == '==========\n':
        break
      else:
        print 'Error: Unknown line:', l[:-1]

  ga = GraphAttribs (edgeLabels=edgeLabels, nodeLabels=nodeLabels,
                     rcNodes=rcNodes, gcNodes=gcNodes)
  return (edges, ga)


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

  Assert (x[0] == reverseMultigraph(reverseMultigraph(x[0])))
