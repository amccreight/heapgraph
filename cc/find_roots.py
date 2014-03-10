#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from collections import namedtuple
import parse_cc_graph
import argparse


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
                    help='garbage collector graph file name')

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


# explain why a root is a root
def explain_root (args, revg, ga, num_known, roots, root):
  print '    Root', root,

  if roots[root] == 'gcRoot':
    print 'is a marked GC object.'
    return
  elif roots[root] == 'stopNodeLabel':
    print 'is an extra root class.'
    return

  assert(roots[root] == 'rcRoot')
  print 'is a ref counted object with', ga.rcNodes[root] - num_known[root], \
      'unknown edge(s).'

  if root in revg:
    print '    known edges:'
    for e in revg[root]:
      print '       ',
      print_node(ga, e)
      print ' ',
      print_edge(args, ga, e, root)
      sys.stdout.write (' {0}\n'.format(root))

# print out the path to an object that has been discovered
def print_path (args, revg, ga, num_known, roots, x, path):
  for p in path:
    print_node(ga, p[0])
    sys.stdout.write('\n    ')
    print_edge(args, ga, p[0], p[1])
    sys.stdout.write(' ')
  print_node(ga, x)
  print
  print
  if path == []:
    explain_root(args, revg, ga, num_known, roots, x)
  else:
    explain_root(args, revg, ga, num_known, roots, path[0][0])
  print



def print_simple_node (ga, x):
  sys.stdout.write ('[{0}]'.format(ga.nodeLabels.get(x, '')))

# produce a simplified version of the path, with the intent of
# eliminating differences that are uninteresting with a large set of
# paths.
def print_simple_path (args, revg, ga, roots, x, path):
  for p in path:
    print_simple_node(ga, p[0])
    sys.stdout.write(' ')
    print_edge(args, ga, p[0], p[1])
    sys.stdout.write(' ')
  print_simple_node(ga, x)
  print


def print_reverse_simple_path (args, revg, ga, roots, x, path):
  print_simple_node(ga, x)
  for p in path:
    sys.stdout.write(' ')
    print_edge(args, ga, p[0], p[1])
    sys.stdout.write(' ')
    print_simple_node(ga, p[0])
  print


def print_roots_only_path(x, path):
  if len(path) != 0:
    print path[-1][0]
  else:
    print x

# look for roots and print out the paths to the given object
def findRoots (args, revg, ga, num_known, roots, x):
  visited = set([])
  path = []
  anyFound = [False]

  def findRootsDFS (y):
    if y in visited:
      return False
    visited.add(y)

    if y in roots:
      if args.print_roots_only:
        print_roots_only_path(x, path)
      elif args.simple_path:
        if args.print_reverse:
          print_reverse_simple_path(args, revg, ga, roots, x, path)
        else:
          path.reverse()
          print_simple_path(args, revg, ga, roots, x, path)
          path.reverse()
      else:
        path.reverse()
        print_path(args, revg, ga, num_known, roots, x, path)
        path.reverse()
      anyFound[0] = True
    else:
      if not y in revg:
        return False
      path.append(None)
      for z in revg[y]:
        path[-1] = (z, y)
        if findRootsDFS(z):
          return True
      path.pop()
    return False

  if not (x in revg or x in roots):
    sys.stdout.write ('No other nodes point to {0} and it is not a root.\n\n'.format(x))
    return

  findRootsDFS(x)

  if not anyFound[0] and not args.print_roots_only:
    print 'No roots found for', x


def reverseGraph (g):
  g2 = {}
  sys.stderr.write('Reversing graph. ')
  for src, dsts in g.iteritems():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  sys.stderr.write('Done.\n\n')
  return g2


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

  for x in g.keys():
    if not args.ignore_rc_roots and x in res[0]:
      roots[x] = 'rcRoot'
    elif not args.ignore_js_roots and ga.gcNodes.get(x, False):
      roots[x] = 'gcRoot'
    elif ga.nodeLabels.get(x, '') == args.node_roots:
      roots[x] = 'stopNodeLabel'

  return roots


def selectTargets (g, ga, target):
  # won't work on windows if you are searching for an address that starts with anything besides 0
  if target[0] == '0':
    return [target]

  targs = []

  # Magic target: look for an nsFrameLoader with a refcount of 1.
  if target == 'nsFrameLoader1':
    target = 'nsFrameLoader'
    for x in g.keys():
      if ga.nodeLabels.get(x, '')[0:len(target)] == target and ga.rcNodes[x] == 1:
        targs.append(x)
    if len(targs) == 0:
      print('Didn\'t find any nsFrameLoaders with refcount of 1')
      exit(-1)
    return targs

  # look for objects with a class name prefix, not a particular object
  for x in g.keys():
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
  revg = reverseGraph(g)

  targs = selectTargets(g, ga, args.target)

  for a in targs:
    if a in g:
      findRoots(args, revg, ga, res[0], roots, a)
    else:
      sys.stderr.write('{0} is not in the graph.\n'.format(a))


if __name__ == "__main__":
  findCCRoots()
