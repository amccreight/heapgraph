#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import copy
import sys
from collections import deque
from collections import namedtuple
from . import parse_cc_graph
import argparse
import re


# Find the objects that are rooting a particular object (or objects of
# a certain class) in the cycle collector graph
#
# This works by reversing the graph, then flooding to find roots.
#
# There are various options to alter what is treated as a root, but
# these are mostly experimental, so they may not produce particularly
# useful results.
#
# --node-name-as-root nsRange (for example) will treat all objects
# with the node name nsRange as roots.  This is useful if a previous
# analysis has determined that a leak always involves an object being
# held onto by a certain class, and you want to continue with manual
# analysis starting at that object.



# Command line arguments

parser = argparse.ArgumentParser(description='Find what is rooting an object in the cycle collector graph.')

parser.add_argument('file_name',
                    help='cycle collector graph file name')

parser.add_argument('target',
                    help='address of target object or prefix of class name of targets')

parser.add_argument('--simple-path', '-sp', dest='simple_path', action='store_true',
                    default=False,
                    help='Print paths on a single line and remove addresses to help large-scale analysis of paths.')

parser.add_argument('--print-reverse', '-r', dest='print_reverse', action='store_true',
                    default=False,
                    help='Display paths in simple mode going from destination to source, rather than from source to destination.')

parser.add_argument('-i', '--ignore-rc-roots', dest='ignore_rc_roots', action='store_true',
                    default=False,
                    help='ignore ref counted roots')

parser.add_argument('-j', '--ignore-js-roots', dest='ignore_js_roots', action='store_true',
                    default=False,
                    help='ignore Javascript roots')

parser.add_argument('-n', '--node-name-as-root', dest='node_roots',
                    metavar='CLASS_NAME',
                    help='treat nodes with this class name as extra roots')

parser.add_argument('--print-roots-only', '-ro', dest='print_roots_only', action='store_true',
                    default=False,
                    help='Only print out the addresses of rooting objects, to simplify use from other programs.')

parser.add_argument('--output-to-file', dest='output_to_file', action='store_true',
                    default=False,
                    help='Print the results to a file. This only works correctly with --print-rooots-only.')

parser.add_argument('--weak-maps', dest='weak_maps', action='store_true',
                    default=False,
                    help='Enable experimental weak map support in DFS mode. WARNING: this may not give accurate results.')

parser.add_argument('--weak-maps-maps-live', dest='weak_maps_maps_live', action='store_true',
                    default=False,
                    help='Pretend all weak maps are alive in DFS mode. Implies --weak-maps. WARNING: this may not give accurate results.')

parser.add_argument('--depth-first', '-dfs', dest='use_dfs', action='store_true',
                    default=False,
                    help='Use the old depth-first algorithm for finding paths.')

parser.add_argument('--hide-weak-maps', '-hwm', dest='hide_weak_maps', action='store_true',
                    default=False,
                    help='If selected, don\'t show why any weak maps in the path are alive.')

# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))

# print an edge description
def print_edge (args, ga, x, y):
  def print_edge_label (l):
    if len(l) == 2:
      l = l[0]
    sys.stdout.write(l)

  if args.print_reverse:
    sys.stdout.write('<--[')
    temp = x
    x = y
    y = temp
  else:
    sys.stdout.write('--[')

  lbls = ga.edgeLabels.get(x, {}).get(y, [])
  if len(lbls) != 0:
    print_edge_label(lbls[0])
    for l in lbls[1:]:
      sys.stdout.write(', ')
      print_edge_label(l)

  if args.print_reverse:
    sys.stdout.write(']--')
  else:
    sys.stdout.write(']-->')


def printKnownEdges(args, knownEdges, ga, x):
  if not knownEdges:
    return

  print('    known edges:')
  for e in knownEdges:
    print('       ', end=' ')
    print_node(ga, e)
    print(' ', end=' ')
    print_edge(args, ga, e, x)
    sys.stdout.write (' {0}\n'.format(x))


# explain why a root is a root
def explainRoot(args, knownEdgesFn, ga, num_known, roots, root):
  print('    Root', root, end=' ')

  if roots[root] == 'gcRoot':
    print('is a marked GC object.')
    if root in ga.incrRoots:
      print('    It is an incremental root, which means it was touched during an incremental CC.')
    return
  elif roots[root] == 'stopNodeLabel':
    print('is an extra root class.')
    return

  assert(roots[root] == 'rcRoot')

  if root in num_known:
    num_unknown = ga.rcNodes[root] - num_known[root]
  else:
    assert(root in ga.incrRoots);
    num_unknown = 0

  print('is a ref counted object with', num_unknown, 'unknown edge(s).')

  printKnownEdges(args, knownEdgesFn(root), ga, root)

  if root in ga.incrRoots:
    print('    It is an incremental root, which means it was touched during an incremental CC.')


# print out the path to an object that has been discovered
def printPathBasic(args, knownEdgesFn, ga, num_known, roots, path):
  print_node(ga, path[0])
  sys.stdout.write('\n')
  prev = path[0]

  for p in path[1:]:
    sys.stdout.write('    ')
    print_edge(args, ga, prev, p)
    sys.stdout.write(' ')
    print_node(ga, p)
    sys.stdout.write('\n')
    prev = p

  print()

  explainRoot(args, knownEdgesFn, ga, num_known, roots, path[0])
  print()

def print_simple_node (ga, x):
  sys.stdout.write ('[{0}]'.format(ga.nodeLabels.get(x, '')))

# produce a simplified version of the path, with the intent of
# eliminating differences that are uninteresting with a large set of
# paths.
def print_simple_path(args, ga, path):
  print_simple_node(ga, path[0])
  prev = path[0]

  for p in path[1:]:
    sys.stdout.write(' ')
    print_edge(args, ga, prev, p)
    sys.stdout.write(' ')
    print_simple_node(ga, p)
    prev = p

  print()

def print_roots_only_path(f, path):
  f.write(path[0])
  f.write('\n')

def printPath(args, knownEdgesFn, ga, num_known, roots, path):
  if args.print_roots_only:
    print_roots_only_path(args.output_file, path)
  elif args.simple_path:
    if args.print_reverse:
      path.reverse()
    print_simple_path(args, ga, path)
  else:
    printPathBasic(args, knownEdgesFn, ga, num_known, roots, path)


########################################################
# Breadth-first shortest path finding.
########################################################

def findRootsBFS(args, g, ga, num_known, roots, target):
  workList = deque()
  distances = {}
  limit = -1

  def traverseWeakMapEntry(dist, k, m, v, lbl):
    if not k in distances or not m in distances:
      # Haven't found either the key or map yet.
      return

    if distances[k][0] > dist or distances[m][0] > dist:
      # Either the key or the weak map is farther away, so we
      # must wait for the farther one before processing it.
      return

    if v in distances:
      assert distances[v][0] <= dist + 1
      return

    distances[v] = (dist + 1, k, m, lbl)
    workList.append(v)


  # For now, ignore keyDelegates.
  weakData = {}
  for wme in ga.weakMapEntries:
    weakData.setdefault(wme.weakMap, set([])).add(wme)
    weakData.setdefault(wme.key, set([])).add(wme)
    if wme.keyDelegate != '0x0':
      weakData.setdefault(wme.keyDelegate, set([])).add(wme)

  # Create a fake start object that points to the roots and
  # add it to the graph.
  startObject = 'FAKE START OBJECT'
  rootEdges = set([])
  for r in roots:
    rootEdges.add(r)

  assert not startObject in g
  g[startObject] = rootEdges
  distances[startObject] = (-1, None)
  workList.append(startObject)

  # Search the graph.
  while workList:
    x = workList.popleft()
    dist = distances[x][0]

    # Check the monotonicity of workList.
    assert dist >= limit
    limit = dist

    if x == target:
      # Found target: nothing to do?
      # This will just find the shortest path to the object.
      continue

    if not x in g:
      # x does not point to any other nodes.
      continue

    newDist = dist + 1
    newDistNode = (newDist, x)

    for y in g[x]:
      if y in distances:
        assert distances[y][0] <= newDist
      else:
        distances[y] = newDistNode
        workList.append(y)

    if x in weakData:
      for wme in weakData[x]:
        assert x == wme.weakMap or x == wme.key or x == wme.keyDelegate
        traverseWeakMapEntry(dist, wme.key, wme.weakMap, wme.value, "value in weak map " + wme.weakMap)
        traverseWeakMapEntry(dist, wme.keyDelegate, wme.weakMap, wme.key, "key delegate in weak map " + wme.weakMap)


  # Print out the paths by unwinding backwards to generate a path,
  # then print the path. Accumulate any weak maps found during this
  # process into the printWorkList queue, and print out what keeps
  # them alive. Only print out why each map is alive once.
  printWorkList = deque()
  printWorkList.append(target)
  printedThings = set([target])

  def knownEdgesFn(node):
    knownEdges = []
    for src, dsts in g.items():
      if node in dsts and src != startObject:
        knownEdges.append(src)
    return knownEdges

  while printWorkList:
    p = printWorkList.popleft()
    path = []
    while p in distances:
      path.append(p)
      dist = distances[p]
      if len(dist) == 2:
        [_, p] = dist
      else:
        # The weak map key is probably more interesting,
        # so follow it, and worry about the weak map later.
        [_, k, m, lbl] = dist

        ga.edgeLabels[k].setdefault(p, []).append(lbl)
        p = k
        if not m in printedThings and not args.hide_weak_maps:
          printWorkList.append(m)
          printedThings.add(m)

    if path:
      assert(path[-1] == startObject)
      path.pop()
      path.reverse()

      print()

      printPath(args, knownEdgesFn, ga, num_known, roots, path)
    else:
      print('Didn\'t find a path.')
      print()
      printKnownEdges(args, knownEdgesFn(p), ga, p)

  del g[startObject]

  return


########################################################
# Depth-first path finding in a reverse graph.
########################################################

def reverseGraph (g):
  g2 = {}
  sys.stderr.write('Reversing graph. ')
  for src, dsts in g.items():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  sys.stderr.write('Done.\n\n')
  return g2

def reverseGraphKnownEdges(revg, target):
  known = []
  for x in revg.get(target, []):
    known.append(x)
  return known

def pretendAboutWeakMaps(args, g, ga):
  def nullToNone(s):
    if s == '0x0':
      return None
    return s

  for wme in ga.weakMapEntries:
    m = nullToNone(wme.weakMap)
    k = nullToNone(wme.key)
    kd = nullToNone(wme.keyDelegate)
    v = nullToNone(wme.value)

    if m and not args.weak_maps_maps_live:
      continue
    if kd:
      continue
    if not k:
      continue
    if not v:
      continue

    g[k].add(v)

    if m:
      edgeLabel = 'weak map key-value edge in map ' + m
    else:
      edgeLabel = 'weak map key-value edge in black map'

    ga.edgeLabels[k].setdefault(v, []).append(edgeLabel)

# Look for roots and print out the paths to the given object.
# This works by reversing the graph, then flooding to find roots.
def findRootsDFS(args, g, ga, num_known, roots, x):
  if args.weak_maps or args.weak_maps_maps_live:
    pretendAboutWeakMaps(args, g, ga)

  revg = reverseGraph(g)
  visited = set([])
  revPath = []
  anyFound = [False]

  def findRootsInner (y):
    if y in visited:
      return False
    visited.add(y)

    if y in roots:
      def knownEdgesFn(node):
        return reverseGraphKnownEdges(revg, node)
      path = copy.copy(revPath)
      path.reverse()
      path.append(x)
      printPath(args, knownEdgesFn, ga, num_known, roots, path)
      anyFound[0] = True
    else:
      if not y in revg:
        return False
      revPath.append(None)
      for z in revg[y]:
        revPath[-1] = z
        if findRootsInner(z):
          return True
      revPath.pop()
    return False

  if not (x in revg or x in roots):
    sys.stdout.write ('No other nodes point to {0} and it is not a root.\n\n'.format(x))
    return

  findRootsInner(x)

  if not anyFound[0] and not args.print_roots_only:
    print('No roots found for', x)
    knownEdges = reverseGraphKnownEdges(revg, x)
    printKnownEdges(args, knownEdges, ga, x)


########################################################
# Top-level file and target selection
########################################################

def loadGraph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  #sys.stdout.write ('Converting to single graph. ')
  #sys.stdout.flush()
  g = parse_cc_graph.toSinglegraph(g)
  sys.stderr.write('Done loading graph. ')
  return (g, ga, res)


def selectRoots(args, g, ga, res):
  roots = {}

  for x in list(g.keys()):
    if not args.ignore_rc_roots and (x in res[0] or x in ga.incrRoots):
      roots[x] = 'rcRoot'
    elif not args.ignore_js_roots and (ga.gcNodes.get(x, False) or x in ga.incrRoots):
      roots[x] = 'gcRoot'
    elif ga.nodeLabels.get(x, '') == args.node_roots:
      roots[x] = 'stopNodeLabel'

  return roots


targetDebug = False
addrPatt = re.compile('[A-F0-9]+$|0x[a-f0-9]+$')


def selectTargets (g, ga, target):
  if addrPatt.match(target):
    if targetDebug:
      print('Address matched.')
      exit(0)
    return [target]
  if targetDebug:
    print('No address found in target.')
    exit(0)

  targs = []

  # Magic target: look for an nsFrameLoader with a refcount of 1.
  if target == 'nsFrameLoader1':
    target = 'nsFrameLoader'
    for x in list(g.keys()):
      if ga.nodeLabels.get(x, '')[0:len(target)] == target and ga.rcNodes[x] == 1:
        targs.append(x)
    if len(targs) == 0:
      print('Didn\'t find any nsFrameLoaders with refcount of 1')
      exit(-1)
    return targs

  # look for objects with a class name prefix, not a particular object
  for x in list(g.keys()):
    if ga.nodeLabels.get(x, '')[0:len(target)] == target:
      targs.append(x)
  if targs == []:
    sys.stderr.write('Didn\'t find any targets.\n')
    #sys.stderr.write('Guessing that argument ' + target + ' is an address.\n')
    #targs = [target]

  return targs


def findCCRoots():
  args = parser.parse_args()

  (g, ga, res) = loadGraph (args.file_name)

  roots = selectRoots(args, g, ga, res)
  targs = selectTargets(g, ga, args.target)

  if args.output_to_file:
    args.output_file = open(args.file_name + '.out', 'w')
  else:
    args.output_file = sys.stdout

  for a in targs:
    if a in g:
      if args.use_dfs:
        findRootsDFS(args, g, ga, res[0], roots, a)
      else:
        print()
        findRootsBFS(args, g, ga, res[0], roots, a)
    else:
      sys.stderr.write('{0} is not in the graph.\n'.format(a))

  if args.output_to_file:
    args.output_file.close()

if __name__ == "__main__":
  findCCRoots()
