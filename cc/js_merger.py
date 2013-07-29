#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# merge JS nodes in a strongly connected component.


import sys
import re
import parse_cc_graph


# combine pre, scc and m into nodeState
#   nodeState represents the hash table mapping pointers
#   the boolean is the low bit of the value being mapped to
def calc_scc (g):
  nodeState = {}
    # if not x in nodeState, x is unvisited
    # nodeState[x] = (True, n)   node open, preorder num of n
    # nodeState[x] = (False, y)  node closed, merge with y
  dfsNum = 0
  rootsStack = []
  openStack = []

  def nonTreeEdge(v):
    nsw = nodeState[v]
    if nsw[0]:
      while nsw[1] < rootsStack[-1]:
        rootsStack.pop()

  for v in g.keys():
    if not v in nodeState:
      controlStack = [v]

      while controlStack != []:
        v = controlStack[-1]
        if v == True:
          # finished the children for the top node
          controlStack.pop()
          vdfs = controlStack.pop()
          v = controlStack.pop()
          # finishNode
          if rootsStack[-1] == vdfs:
            rootsStack.pop()
            while 1:
              w = openStack.pop()
              assert (w in nodeState)
              assert (nodeState[w][0])
              nodeState[w] = (False, v)
              if w == v:
                break
          # /finishNode
        else:
          if v in nodeState:
            controlStack.pop()
            nonTreeEdge(v)
          else:
            # new node
            nodeState[v] = (True, dfsNum)
            # treeEdge
            openStack.append(v)
            rootsStack.append(dfsNum)
            controlStack.append(dfsNum)
            controlStack.append(True)
            # /treeEdge
            dfsNum += 1
            for w in g[v]:
              if w in nodeState:
                nonTreeEdge(w)
              else:
                controlStack.append(w)

  # convert nodeState to a merge map
  m = {}
  for n, ns in nodeState.iteritems():
    assert(not ns[0])
    mergeTo = ns[1]
    if not mergeTo in m:
      m[mergeTo] = []
    m[mergeTo].append(n)

  return m


# convert to a single graph, eliminate non-GCed nodes
def convertGraph (gm, ga):
  g = {}
  for src, dsts in gm.iteritems():
    if not src in ga.gcNodes:
      continue
    d = set([])
    for dst, k in dsts.iteritems():
      if dst in ga.gcNodes:
        d.add(dst)
    g[src] = d
  return g


def loadGraph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  sys.stderr.flush()
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  g = convertGraph(g, ga)
  sys.stderr.write('Done loading graph.\n')
  return (g, ga)


if len(sys.argv) < 2:
  sys.stderr.write('Not enough arguments.')
  exit()


(g, ga) = loadGraph(sys.argv[1])
m = calc_scc(g)

for x, l in m.iteritems():
  if len(l) <= 1:
    continue
  print x,
  for y in l:
    print y,
  print


if False:
  counts = {}

  for x, li in m.iteritems():
    l = len(li)
    counts[l] = counts.get(l, 0) + 1

  print counts

