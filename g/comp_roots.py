#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from collections import namedtuple
import comp_parse_gc_graph
import argparse



# this comment is out of date


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

parser = argparse.ArgumentParser(description='Find a rooting object in the cycle collector graph.')

parser.add_argument('file_name',
                    help='cycle collector graph file name')

parser.add_argument('target',
                    help='address of target object or prefix of class name of targets')

parser.add_argument('--ignore-rc-roots', dest='ignore_rc_roots', action='store_const',
                    const=True, default=False,
                    help='ignore ref counted roots')

parser.add_argument('--ignore-js-roots', dest='ignore_js_roots', action='store_const',
                    const=True, default=False,
                    help='ignore Javascript roots')

parser.add_argument('--node-name-as-root', dest='node_roots',
                    metavar='CLASS_NAME',
                    help='treat nodes with this class name as extra roots')


args = parser.parse_args()



# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels[x]))

# print an edge description
def print_edge (ga, x, y):
  def print_edge_label (l):
    if len(l) == 2:
      l = l[0]
    sys.stdout.write(l)

  sys.stdout.write(ga.compartments[y])
  sys.stdout.write(' ')

  sys.stdout.write('--')
  lbls = ga.edgeLabels.get(x, {}).get(y, [])
  if len(lbls) != 0:
    sys.stdout.write('[')
    print_edge_label(lbls[0])
    for l in lbls[1:]:
      sys.stdout.write(', ')
      print_edge_label(l)
    sys.stdout.write(']')

  sys.stdout.write('->')


def explain_root (ga, root):
  print "via", ga.rootLabels[root], ":"

# print out the path to an object that has been discovered
def print_path (revg, ga, roots, x, path):
  if path == []:
    explain_root(ga, x)
  else:
    explain_root(ga, path[0][0])

  for p in path:
    print_node(ga, p[0])
    sys.stdout.write('\n    ')
    print_edge(ga, p[0], p[1])
    sys.stdout.write(' ')
  print_node(ga, x)
  print
  print


# look for roots and print out the paths to the given object
def findRoots (revg, ga, roots, x):
  visited = set([])
  path = []
  anyFound = [False]

  def findRootsDFS (y):
    if y in visited:
      return False
    visited.add(y)
    if y in roots: # treats black and gray roots as roots
      path.reverse()
      print_path(revg, ga, roots, x, path)
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

  if not x in revg:
    sys.stdout.write ('No other nodes point to {0}.\n\n'.format(x))
    return

  findRootsDFS(x)

  if not anyFound[0]:
    print 'No roots found.'


def reverseGraph (g):
  g2 = {}
  print 'Reversing graph.',
  sys.stdout.flush()
  for src, dsts in g.iteritems():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  print 'Done.'
  print
  return g2

def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = comp_parse_gc_graph.parseGCEdgeFile(fname)
  #sys.stdout.write ('Converting to single graph. ') 
  #sys.stdout.flush()
  g = comp_parse_gc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga)


####################

(g, ga) = loadGraph (args.file_name)
roots = ga.roots
revg = reverseGraph(g)


my_compartment = args.target


if False:
  findRoots(revg, ga, roots, "0x11ac143d0")
  exit(0)


print
print "Looking for compartment", my_compartment

num_roots = 0

if True:
  print "Checking for direct root references to the compartment."

  for x in roots:
    if ga.compartments[x] == my_compartment:
      print_node(ga, x)
      sys.stdout.write(' via ' + ga.rootLabels[x] + "\n")

  print


print "Checking for references from other compartments to the compartment."

for src, dsts in g.iteritems():
  if ga.compartments[src] != my_compartment:
    for d in dsts:
      if ga.compartments[d] == my_compartment:
        print_node(ga, src)
        print " from compartment", ga.compartments[src]
        print "to: ",
        print_node(ga, d)
        print
        findRoots(revg, ga, roots, src)


# first, only consider pointers to a compartment from roots.

# (we should also consider compartments that hold onto other compartments)

# roots are the set of objects reachable from various roots.


# For a given compartment, which other compartments/roots hold onto it?
