#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Compute the dominator tree of a GC graph.

import sys
import re
import parse_gc_graph
import argparse

from types import StringType


parser = argparse.ArgumentParser(description='Compute the dominator tree of a GC log')
parser.add_argument('file_name',
                    help='GC graph file name')
parser.add_argument('--dot', dest='dotFileName', type=str,
                    help='Output a dot file with the given name for use with Graphviz.')
parser.add_argument('--script-split', dest='scriptSplit', action='store_true',
                    help='Group trees by script, if they contain only one script-y thing')

#parser.add_argument('target',
#                    help='address of target object')

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
  workList = [source]

  while workList:
    x = workList.pop()
    if x == ignore:
      continue
    s.add(x)
    children = []
    for y in g.get(x, []):
      if not y in s:
        children.append(y)
    children.reverse()
    workList = workList + children

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

fake_root_label = "root"

def domTreeRoots(g, roots):
  # Set up a fake node for the roots.
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

  work_list = [(source_label, None)]

  # Compute the DFS tree.
  while work_list:
    (x_label, x_parent) = work_list.pop()

    if x_label in label_preorder:
      assert not x_parent is None
      x = label_preorder[x_label]
      rev_g.setdefault(x, []).append(x_parent)
      continue

    x = len(preorder_labels)
    preorder_labels.append(x_label)
    label_preorder[x_label] = x
    sdom[x] = x
    dom[x] = x
    if not x_parent is None:
      tree_parent[x] = x_parent
      rev_g.setdefault(x, []).append(x_parent)

    if not x_label in g:
      continue
    children = []
    for y_label in g[x_label]:
      if y_label == x_label:
        continue
      if not y_label in label_preorder:
        children.append((y_label, x))
      else:
        y = label_preorder[y_label]
        rev_g.setdefault(y, []).append(x)

    children.reverse()
    work_list = work_list + children

  # Compute the semi-dominator and whatever the other thing is.
  bucket = {}
  ds_parent = {}
  path_min = {}

  # XXX recursion. Max depth 180 on an example log.
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

#######

# Graphviz output of a tree.

# Set this to True if using a log that includes my patch to output the
# size of each object in the log.
sizeLabel = True

def nodeLabel(ga, x):
  if x == fake_root_label:
    return fake_root_label
  l = ga.nodeLabels.get(x)
  if sizeLabel and " SIZE::" in l:
    l = l.split(" SIZE:: ")[0]
  if l.endswith(' <no private>'):
    l = l[:-len(' <no private>')]
  return l

def copyReachableTree(ga, tree, roots):
  newTree = {}

  def copyReachableTreeHelper(x):
    assert not x in newTree
    newTree[x] = tree[x]
    for c in newTree[x]:
      if not x in newTree and c in tree:
        copyReachableTreeHelper(c)

  for r in roots:
    copyReachableTreeHelper(r)
  return newTree


def displayLabel(ga, g, sizes, x, lbl):
  if sizeLabel:
    sizeSuffix = " ({} bytes)".format(sizes[x])
  else:
    sizeSuffix = ""

  if lbl == "Object":
    return x + sizeSuffix

  if lbl == "NonSyntacticVariablesObject":
    for y in g[x]:
      if "__URI__" in ga.edgeLabels.get(x, {}).get(y, []):
        yLbl = nodeLabel(ga, y)
        return "NSVO " + (yLbl.split())[-1].split('/')[-1]  + sizeSuffix

  if lbl.startswith("script "):
    return "script " + (lbl.split())[-1].split('/')[-1] + sizeSuffix

  return lbl + sizeSuffix


def computeSizes(ga, tree):
  # This function requires the extra size logging.
  assert sizeLabel

  sizes = {}

  def helper(x):
    if x in sizes:
      return

    mySize = 8
    lbl = ga.nodeLabels.get(x, "")
    if "SIZE::" in lbl:
      lbl = lbl.split("SIZE:: ")
      assert len(lbl) == 2 # XXX This should only happen with my hacky expanded reporting.
      mySize = int(lbl[1])

    for c in tree.get(x, set([])):
      helper(c)
      mySize += sizes[c]

    sizes[x] = mySize

  for x in tree:
    helper(x)
  return sizes


# Look through a DOM tree for any scripts.
def computeScripts(ga, tree):
  # This maps nodes to either:
  # - 1 if the node dominates multiple scripts.
  # - a string with the script name if the node dominates one script.
  # - 0 if the node dominates no scripts.
  scripts = {}

  # XXX recursion. Max depth 141 on an example log.
  def helper(x):
    if x in scripts:
      return scripts[x]

    lbl = nodeLabel(ga, x)
    scriptName = 0
    if lbl.startswith("script "):
      scriptName = (lbl.split())[-1].split('/')[-1].split(':')[0]
    elif lbl == "NonSyntacticVariablesObject":
      for y in g[x]:
        if "__URI__" in ga.edgeLabels.get(x, {}).get(y, []):
          yLbl = nodeLabel(ga, y)
          scriptName = (yLbl.split())[-1].split('/')[-1]
          break

    for c in tree.get(x, set([])):
      newScriptName = helper(c)
      if scriptName == 1 or newScriptName == 1:
        scriptName = 1
        continue
      if scriptName == 0:
        scriptName = newScriptName
        continue
      if newScriptName == 0:
        continue
      assert type(scriptName) is StringType
      assert type(newScriptName) is StringType
      if scriptName != newScriptName:
        scriptName = 1

    scripts[x] = scriptName
    return scriptName


  for x in tree:
    helper(x)

  return scripts


def textSizeTree(args, ga, g, tree):
  showByScripts = args.scriptSplit

  assert sizeLabel

  sizeThreshold = 1000

  if showByScripts:
    scripts = computeScripts(ga, tree)
  sizes = computeSizes(ga, tree)

  def sortedChildren(tree, sizes, x):
    if not x in tree:
      return []
    return sorted(tree[x], reverse=True, key=lambda y: sizes[y])

  def splitByScript():
    scriptTrees = {}
    for x in tree[fake_root_label]:
      scriptTrees.setdefault(scripts[x], []).append(x)

    multiScripts = scriptTrees.get(1, [])
    del scriptTrees[1]
    noScripts = scriptTrees.get(0, [])
    del scriptTrees[0]

    scriptSizes = {}
    for script, trees in scriptTrees.iteritems():
      mySize = 0
      for x in trees:
        mySize += sizes[x]
      scriptSizes[script] = mySize
      #print script, mySize

    for script in sorted(filter(lambda x: scriptSizes[x] >= sizeThreshold, scriptTrees), reverse=True,
                         key=lambda x: scriptSizes[x]):
      print "{} ({} bytes)".format(script, scriptSizes[script])
      print '------------------------------'
      for x in sortedChildren(scriptTrees, sizes, script):
        if helper(x, 0):
          sys.stdout.write("\n")
      print

    if multiScripts:
      print 'Multiple scripts'
      print '----------------'
      for x in sorted(multiScripts, reverse=True, key=lambda y: sizes[y]):
        if helper(x, 0):
          sys.stdout.write("\n")
      print

    if noScripts:
      print 'No script found'
      print '---------------'
      for x in sorted(noScripts, reverse=True, key=lambda y: sizes[y]):
        if helper(x, 0):
          sys.stdout.write("\n")
      print


  def helper(x, depth):
    xSize = sizes[x]
    if xSize < sizeThreshold:
      return False
    lbl = nodeLabel(ga, x)
    if lbl == "shape":
      return False
    sys.stdout.write("|")
    for i in range(depth):
      sys.stdout.write("--")
    lbl = displayLabel(ga, g, sizes, x, lbl)
    sys.stdout.write(" " + lbl)
    sys.stdout.write("\n")

    for y in sortedChildren(tree, sizes, x):
      helper(y, depth + 1)

    return True


  if showByScripts:
    splitByScript()
  else:
    for x in sortedChildren(tree, sizes, fake_root_label):
      if helper(x, 0):
        sys.stdout.write("\n")


def graphTree(args, ga, g, tree, childCounts):
  domLimit = 20
  skipShape = True

  if sizeLabel:
    sizes = computeSizes(ga, tree)

  # XXX Only keep nodes dominated by the self-hosting global.
  #for x in tree:
  #  if nodeLabel(ga, x) == "self-hosting-global":
  #    tree = copyReachableTree(ga, tree, x)
  #    break

  #newRoots = []
  #for x in tree:
  #  lbl = nodeLabel(ga, x)
  #  if lbl == "LexicalEnvironment" or lbl == "NonSyntacticVariablesObject":
  #    newRoots.append(x)
  #tree = copyReachableTree(ga, tree, newRoots)

  f = open(args.dotFileName, "w")
  f.write("digraph G {\n")
  for x, children in tree.iteritems():
    if x == fake_root_label or childCounts[x] < domLimit:
      continue
    lbl = nodeLabel(ga, x)
    if skipShape and lbl == 'shape':
      continue
    anyTrimmed = False
    for c in children:
      if childCounts[c] < domLimit or (skipShape and nodeLabel(ga, c) == 'shape'):
        anyTrimmed = True
        continue
      f.write("  N{} -> N{} [len=1];\n".format(x, c))
      # XXX print out a label somehow....
    if anyTrimmed:
      count = " " + str(childCounts[x])
    else:
      count = ""

    displayLbl = displayLabel(ga, g, sizes, x, lbl)

    if sizeLabel:
      displayLbl += " ({} bytes)".format(sizes[x])
    f.write('  N{} [label="{}{}"]\n'.format(x, displayLbl, count))

  f.write("}\n")
  f.close()


#######

def loadGraph(fname):
  sys.stdout.write('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = parse_gc_graph.parseGCEdgeFile(fname)
  g = parse_gc_graph.toSinglegraph(g)
  sys.stdout.write('Done loading graph.\n')
  sys.stdout.flush()

  return (g, ga)


def getNumChildren(ga, t):
  childCounts = {}

  def getNumChildrenHelper(x):
    total = 0
    for y in t.get(x, []):
      total += getNumChildrenHelper(y) + 1
    childCounts[x] = total
    return total

  getNumChildrenHelper(fake_root_label)

  del childCounts[fake_root_label]

  return childCounts

  #counts = {}
  #for x, n in childCounts.iteritems():
  #  counts.setdefault(n, []).append(x)

  #n = 0
  #for x in reversed(sorted(counts.keys())):
  #  for c in counts[x]:
  #    print x, c, ga.nodeLabels[c]




if __name__ == "__main__":
  source_label = 'A'
  label_preorder = {}

  g = {'A': ['B', 'C'],
       'B': ['D', 'E']}

  preorder_labels = []

  if False:
    def dfsVisit(x_label):
      x = len(preorder_labels)
      print x_label, "->", x
      preorder_labels.append(x_label)
      label_preorder[x_label] = x
      if not x_label in g:
        return
      for y_label in g[x_label]:
        if y_label == x_label:
          continue
        if not y_label in label_preorder:
          dfsVisit(y_label)
          y = label_preorder[y_label]
        else:
          y = label_preorder[y_label]

    dfsVisit(source_label)
  elif False:
    work_list = [(source_label, None)]
    while work_list:
      print work_list
      (x_label, x_parent) = work_list.pop()
      x = len(preorder_labels)
      print x_label, "->", x
      preorder_labels.append(x_label)
      label_preorder[x_label] = x

      if not x_label in g:
        continue
      children = []
      for y_label in g[x_label]:
        if y_label == x_label:
          continue
        if not y_label in label_preorder:
          children.append((y_label, x))
        else:
          y = label_preorder[y_label]

      children.reverse()
      work_list = work_list + children

  if True:
    args = parser.parse_args()
    (g, ga) = loadGraph(args.file_name)
    t = domTreeRoots(g, ga.roots)

    if args.dotFileName:
      childCounts = getNumChildren(ga, t)
      graphTree(args, ga, g, t, childCounts)
    else:
      textSizeTree(args, ga, g, t)

    #for node, children in t.iteritems():
    #  print node, ' '.join(children)

    #print t.keys()
    #print t[args.target]

  else:
    # Simple test cases.
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

    # Small chunk of g2 example.
    g3 = ("R",
          {
            "R": ["B", "A"],
            "A": ["D"],
            "B": ["A", "D"],
            "D": ["R"],
          })

    g = g2
    checkDomTree(g[1], g[0])


