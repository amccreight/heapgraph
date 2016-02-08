#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple


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
  roots = set([])
  rootLabels = {}
  blackRoot = True;

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
        roots.add(addr)
        rootLabels[lbl] = rootLabels.setdefault(lbl, 0) + 1
    else:
      wmm = weakMapEntryPatt.match(l)
      if wmm:
        # Don't do anything with weak map entries for now.
        continue
      elif l[:10] == '==========':
        break
      elif l[0] == '#':
        # Skip over comments.
        continue
      else:
        print "Error: unknown line ", l
        exit(-1)

  for r, count in rootLabels.iteritems():
    print r, count

  return rootLabels


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

  rootLabels = parseRoots(f)
  exit(0)

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


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseGCEdgeFile(sys.argv[1])


