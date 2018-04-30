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


def printTree(t):
  for x, children in t.iteritems():
    print "{}: {}".format(x, " ".join(children))

def setTree(t):
  return frozenset([(x, frozenset(c)) for (x, c) in t.iteritems()])

def checkDomTree(g, source):
  t1 = slowDomTree(g, source)
  t2 = domTree(g, source)
  print "slow:", t1
  print
  print "fast:", t2
  assert setTree(t1) == setTree(t2)


####

def computeReachable(g, source, ignore):
  s = set()
  def dfs(x):
    if x == ignore:
      return
    s.add(x)
    for y in g.get(x, []):
      if not y in s:
        dfs(y)
  dfs(source)
  return s

# Compute the dominator tree, but using the naive algorithm.
def slowDomTree(g, source):
  reachable = computeReachable(g, source, None)
  dom = {}
  inv_dom = {}
  # Compute the dominance relation.
  for x in reachable:
    for y in reachable.difference(computeReachable(g, source, x)):
      if x != y:
        dom.setdefault(x, []).append(y)
        inv_dom.setdefault(y, []).append(x)

  # Compute the immediate dominance relation.
  tree = {}
  for x, dom_by in inv_dom.iteritems():
    candidate_idom = None
    for y in dom_by:
      dom_y_can = candidate_idom and candidate_idom in dom.get(y)
      dom_can_y = not candidate_idom or y in dom.get(candidate_idom, [])
      assert dom_y_can != dom_can_y
      if dom_y_can:
        continue
      candidate_idom = y
    assert candidate_idom
    tree.setdefault(candidate_idom, []).append(x)

  return tree


####

def domTreeRoots(g, roots):
  # Set up a fake node for the roots.
  fake_root_label = "root"
  assert not fake_root_label in g
  g[fake_root_label] = []
  for r in roots:
    g[fake_root_label].append(r)
  return domTree(g, fake_root_label)


# Lengauer and Tarjan dominator tree algorithm.

def domTree(g, source_label):
  # Compute the DFS tree.
  tree_parent = {} # par
  preorder_labels = [] # rev
  label_preorder = {} # arr
  dom = {}
  sdom = {}
  rev_g = {} # rg

  # Compute the DFS tree.
  def dfsVisit(x_label):
    x = len(preorder_labels)
    preorder_labels.append(x_label)
    label_preorder[x_label] = x
    sdom[x] = x
    dom[x] = x
    if not x_label in g:
      return
    for y_label in g[x_label]:
      if y_label == x_label:
        continue
      if not y_label in label_preorder:
        dfsVisit(y_label)
        y = label_preorder[y_label]
        tree_parent[y] = x
      else:
        y = label_preorder[y_label]
      rev_g.setdefault(y, []).append(x)

  dfsVisit(source_label)

  # Compute the semi-dominator and whatever the other thing is.
  bucket = {}
  ds_parent = {}
  path_min = {}

  def find(x):
    if not x in ds_parent:
      return x
    if ds_parent[x] in ds_parent:
      path_min[x] = min(path_min[x], find(ds_parent[x]))
      ds_parent[x] = ds_parent[ds_parent[x]]
    return path_min[x]

  for y in reversed(xrange(1, len(preorder_labels))):
    for x in rev_g.get(y, []):
      sdom[y] = min(sdom[y], sdom[find(x)])
    bucket.setdefault(sdom[y], []).append(y)

    assert not y in ds_parent
    ds_parent[y] = tree_parent[y]
    path_min[y] = sdom[y]
    if not tree_parent[y] in bucket:
      continue
    for w in bucket[tree_parent[y]]:
      v = find(w)
      dom[w] = v if sdom[v] < sdom[w] else tree_parent[y]
    del bucket[tree_parent[y]]

  # Do the final calculation.
  tree = {}
  for x in xrange(1, len(preorder_labels)):
    if dom[x] != sdom[x]:
      dom[x] = dom[dom[x]]
    x_label = preorder_labels[x]
    dom_x_label = preorder_labels[dom[x]]
    tree.setdefault(dom_x_label, []).append(x_label)

  return tree


def loadGraph(fname):
  sys.stdout.write('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = parse_gc_graph.parseGCEdgeFile(fname)
  g = parse_gc_graph.toSinglegraph(g)
  sys.stdout.write('Done loading graph.\n')
  sys.stdout.flush()

  return (g, ga)


if __name__ == "__main__":

  if True:
    args = parser.parse_args()
    (g, ga) = loadGraph(args.file_name)
    print domTreeRoots(g, ga.roots)
  elif True:
    g1 = ("c",
          {
            "a": ["b"],
            "b": ["c", "d"],
            "c": ["e"],
            "d": ["e"],
            "e": ["a"],
          })

    # Example from https://tanujkhattar.wordpress.com/2016/01/11/dominator-tree-of-a-directed-graph/
    g2 = ("R",
          {
            "R": ["C", "B", "A"],
            "A": ["D"],
            "B": ["E", "A", "D"],
            "C": ["F", "G"],
            "D": ["L"],
            "E": ["H"],
            "F": ["I"],
            "G": ["I", "J"],
            "H": ["K", "E"],
            "I": ["K"],
            "J": ["I"],
            "K": ["R", "I"],
            "L": ["H"],
          })
    g = g2
    checkDomTree(g[1], g[0])


