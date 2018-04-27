#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Compute the dominator tree of a GC graph.

import sys
import re
import parse_gc_graph
import argparse


parser = argparse.ArgumentParser(description='Compute the dominator tree of a GC log')
parser.add_argument('file_name',
                    help='GC graph file name')


#######
# union find with path compression and union by rank

def findi (m, x):
  if not x in m:
    m[x] = [x, 0]
    return m[x]
  if m[x][0] == x:
    return m[x]
  z = findi (m, m[x][0])
  m[x] = z
  return z

def find (m, x):
  return findi(m, x)[0]

def union (m, rep, x, y):
  xp = findi (m, x)
  yp = findi (m, y)
  if xp == yp:
    return
  if xp[1] < yp[1]:
    rep[yp[0]] = rep.get(xp[0], xp[0])
    if xp[0] in rep:
      del rep[xp[0]]
    m[xp[0]][0] = yp[0]
  elif xp[1] > yp[1]:
    m[yp[0]][0] = xp[0]
  else:
    m[yp[0]][0] = xp[0]
    m[xp[0]][1] += 1


####

def doStuff(g, roots):
    tree_parent = {} # par
    preorder_labels = ["root"] # rev
    label_preorder = {"root": 0} # arr
    sdom = {}
    rev_g = {} # rg

    # Compute the DFS tree.
    def dfsVisit(x_label):
        x = len(preorder_labels)
        preorder_labels.append(x_label)
        label_preorder[x_label] = x
        sdom[x] = x
        for y_lbl in g.get(x_label, []):
            if y_lbl == x_lbl:
                continue
            if not y_lbl in label_preorder:
                dfsVisit(y_lbl)
                y = label_preorder[y_lbl]
                tree_parent[y] = x
            else:
                y = label_preorder[y_lbl]
            rev_g.setdefault(y, []).append(x)

    for r in roots:
        if not r in label_preorder:
            dfsVisit(r)
            tree_parent[label_preorder[r]] = 0

    # Compute the sdom and whatever the other thing is.
    bucket = {}
    uf_merge = {}
    uf_rep = {}

    for y in reversed(xrange(len(preorder_labels))):
        for x in rev_g[y]:
            sdom[y] = min(sdom[y], sdom[find(uf_merge, x)])
            if y > 0:
                bucket[sdom[y]].append(y)


def loadGraph(fname):
  sys.stdout.write('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = parse_gc_graph.parseGCEdgeFile(fname)
  g = parse_gc_graph.toSinglegraph(g)
  sys.stdout.write('Done loading graph.\n')
  sys.stdout.flush()

  return (g, ga)


if __name__ == "__main__":
  #args = parser.parse_args()
  #(g, ga) = loadGraph(args.file_name)

  g = {}
  g["a"] = ["b", "c"]
  g["b"] = ["b1", "b2"]

  doStuff(g, ["a"])
