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

