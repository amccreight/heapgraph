#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple
from collections import deque
import parse_gc_graph
import argparse
from dotify_paths import outputDotFile
from dotify_paths import add_dot_mode_path

########################################################
# Find the objects that are rooting a particular object
# (or objects of a certain class) in a Firefox garbage
# collector log.
########################################################



########################################################
# Command line arguments.
########################################################

parser = argparse.ArgumentParser(description='Find out what is rooting an object in the garbage collector graph.')

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

parser.add_argument('--num-paths', '-np', type=int, dest='max_num_paths',
                    help='Only print out the first so many paths for each target.')

parser.add_argument('--black-roots-only', '-bro', dest='black_roots_only', action='store_true',
                    default=False,
                    help='If this is set, only trace from black roots.  Otherwise, also trace from gray roots.')

parser.add_argument('--string-mode', '-sm', dest='string_mode', action='store_true',
                    default=False,
                    help='Match any string that has as a prefix the target passed in as the second argument.')

parser.add_argument('--breadth-first', '-bfs', dest='use_bfs', action='store_true',
                    default=False,
                    help='Use the experimental breadth-first search shortest path algorithm for path finding.')

### Dot mode arguments.
parser.add_argument('--dot-mode', '-d', dest='dot_mode', action='store_true',
                    default=False,
                    help='Experimental dot mode.  Outputs to graph.dot.')
# Convert dot file to a PDF with 'sfdp -Gsize=67! -Goverlap=prism -Tpdf -O graph.dot'
# 'neato' works pretty well too, in place of sfdp.

parser.add_argument('--dot-mode-edges', '-de', dest='dot_mode_edges', action='store_true',
                    default=False,
                    help='Show edges in dot mode.')



########################################################
# Path printing
########################################################

addrPatt = re.compile('[A-F0-9]+$|0x[a-f0-9]+$')


# print a node description
def print_node(ga, x):
  # truncate really long nodeLabels.
  sys.stdout.write('{0} [{1}]'.format(x, ga.nodeLabels[x][:50]))

# print an edge description
def print_edge(args, ga, x, y):
  def print_edge_label(l):
    if len(l) == 2:
      l = l[0]
    sys.stdout.write(l)

  if args.print_reverse:
    sys.stdout.write('<--')
  else:
    sys.stdout.write('--')

  lbls = ga.edgeLabels.get(x, {}).get(y, [])
  if len(lbls) != 0:
    sys.stdout.write('[')
    print_edge_label(lbls[0])
    for l in lbls[1:]:
      sys.stdout.write(', ')
      print_edge_label(l)
    sys.stdout.write(']')

  if args.print_reverse:
    sys.stdout.write('--')
  else:
    sys.stdout.write('-->')


def explain_root(ga, root):
  print "via", ga.rootLabels[root], ":"

# print out the path to an object that has been discovered
def basic_print_path(args, ga, roots, x, path):
  if path == []:
    explain_root(ga, x)
  else:
    explain_root(ga, path[0][0])

  for p in path:
    print_node(ga, p[0])
    sys.stdout.write('\n    ')
    print_edge(args, ga, p[0], p[1])
    sys.stdout.write(' ')

  print_node(ga, x)
  print
  print


def print_simple_node(ga, x):
  l = ga.nodeLabels[x][:50]
  if l.endswith(' <no private>'):
    l = l[:-13]
  sys.stdout.write('[{0}]'.format(l))

def simple_explain_root(ga, root):
  # This won't work on Windows.
  l = re.sub(r'0x[0-9a-f]{8}', '*', ga.rootLabels[root])
  #l = addrPatt.sub("ADDR", ga.rootLabels[root])
  #l = ga.rootLabels[root]
  print "via", l, ":",

# produce a simplified version of the path, with the intent of
# eliminating differences that are uninteresting with a large set of
# paths.
def print_simple_path(args, ga, roots, x, path):
  if path == []:
    simple_explain_root(ga, x)
  else:
    simple_explain_root(ga, path[0][0])

  for p in path:
    print_simple_node(ga, p[0])
    sys.stdout.write(' ')
    print_edge(args, ga, p[0], p[1])
    sys.stdout.write(' ')
  print_simple_node(ga, x)
  print


def print_reverse_simple_path(args, ga, roots, x, path):
  print_simple_node(ga, x)
  for p in path:
    sys.stdout.write(' ')
    print_edge(args, ga, p[0], p[1])
    sys.stdout.write(' ')
    print_simple_node(ga, p[0])

  sys.stdout.write(' ')
  if path == []:
    simple_explain_root(ga, x)
  else:
    simple_explain_root(ga, path[-1][0])
  print


def print_path(args, ga, roots, x, path):
  if args.simple_path:
    if args.print_reverse:
      print_reverse_simple_path(args, ga, roots, x, path)
    else:
      path.reverse()
      print_simple_path(args, ga, roots, x, path)
      path.reverse()
  elif args.dot_mode:
    path.reverse()
    add_dot_mode_path(ga, roots, x, path)
    path.reverse()
  else:
    path.reverse()
    basic_print_path(args, ga, roots, x, path)
    path.reverse()



########################################################
# Breadth-first shortest path finding.
########################################################

def findRootsBFS(args, g, ga, target):
  workList = deque()
  distances = {}
  limit = -1

  # Create a fake start object that points to the roots and
  # add it to the graph.
  startObject = 'FAKE START OBJECT'
  rootEdges = set([])
  for r in ga.roots:
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
    newDistNode = (dist + 1, x)

    for y in g[x]:
      if y in distances:
        assert distances[y][0] <= newDist
      else:
        distances[y] = newDistNode
        workList.append(y)

  path = []
  p = target
  while p in distances:
    path.append(p)
    [_, p] = distances[p]

  assert(path[-1] == startObject)
  path.pop()
  path.reverse()

  print path

  return



########################################################
# Depth-first path finding in a reverse graph.
########################################################

def reverseGraph(g):
  g2 = {}
  print 'Reversing graph.',
  sys.stdout.flush()
  for src, dsts in g.iteritems():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  print 'Done.'
  print
  return g2


# Look for roots and print out the paths to the given object
# This works by reversing the graph, then flooding to find roots.
def findRootsDFS(args, g, ga, roots, x):
  revg = reverseGraph(g)
  visited = set([])
  path = []
  numPathsFound = [0]

  def findRootsDFSHelper(y):
    if y in visited:
      return False
    visited.add(y)
    if y in roots and (not args.black_roots_only or roots[y]): # roots[y] is true for black roots
      if args.max_num_paths == None or numPathsFound[0] < args.max_num_paths:
        print_path(args, ga, roots, x, path)
      numPathsFound[0] += 1

    # Whether or not y is a root, we want to find other paths to y.
    if not y in revg:
      return False
    path.append(None)
    for z in revg[y]:
      path[-1] = (z, y)
      if findRootsDFSHelper(z):
        return True
    path.pop()
    return False

  if not (x in revg or x in roots):
    sys.stdout.write('No other nodes point to {0} and it is not a root.\n\n'.format(x))
    return

  findRootsDFSHelper(x)

  if numPathsFound[0] == 0:
    print 'No roots found.'
  elif args.max_num_paths == None or numPathsFound[0] <= args.max_num_paths:
    print 'Found and displayed', numPathsFound[0], 'paths.'
  else:
    print 'Displayed', args.max_num_paths, 'out of', numPathsFound[0], 'total paths found.'


########################################################
# Top-level file and target selection
########################################################

def loadGraph(fname):
  sys.stdout.write('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = parse_gc_graph.parseGCEdgeFile(fname)
  #sys.stdout.write('Converting to single graph. ')
  #sys.stdout.flush()
  g = parse_gc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga)


def stringTargets(ga, stringTarget):
  targs = []

  for addr, lbl in ga.nodeLabels.iteritems():
    if not lbl.startswith('string '):
      continue
    s = lbl[7:]
    if s.startswith(stringTarget):
      targs.append(addr)

  sys.stderr.write('Found {} string targets starting with {}\n'.format(len(targs), stringTarget))
  return targs


targetDebug = False

def selectTargets(args, g, ga):
  if args.string_mode:
    targs = stringTargets(ga, args.target)
  elif addrPatt.match(args.target):
    targs = [args.target]
    if targetDebug:
      sys.stderr.write('Looking for object with address {}.\n'.format(args.target))
  else:
    # look for objects with a class name prefixes, not a particular object
    targs = []
    for x in g.keys():
      if ga.nodeLabels.get(x, '')[0:len(args.target)] == args.target:
        if targetDebug:
          sys.stderr.write('Found object {}. '.format(x))
        targs.append(x)
    if targs == []:
      print 'No matching class names found.'
    else:
      if targetDebug:
        sys.stderr.write('\n')

  return targs


def findGCRoots():
  args = parser.parse_args()

  (g, ga) = loadGraph(args.file_name)
  roots = ga.roots

  targs = selectTargets(args, g, ga)

  for a in targs:
    if a in g:
      if args.use_bfs:
        findRootsBFS(args, g, ga, a)
      else:
        findRootsDFS(args, g, ga, roots, a)
    else:
      sys.stdout.write('{0} is not in the graph.\n'.format(a))

  if args.dot_mode:
    outputDotFile(args, ga, targs)


if __name__ == "__main__":
  findGCRoots()
