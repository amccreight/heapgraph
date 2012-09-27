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
    else:
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
