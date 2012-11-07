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

import sys
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser


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

usage = "usage: %prog [options] file_name target\n\
  file_name is the name of the cycle collector graph file\n\
  target is the object(s) to look for\n\
  target can be an address or a prefix of a object name"
parser = OptionParser(usage=usage)

parser.add_option("-i", '--ignore-rc-roots', dest='ignore_rc_roots', action='store_true',
                  default=False,
                  help='ignore ref counted roots')

parser.add_option("-j", '--ignore-js-roots', dest='ignore_js_roots', action='store_true',
                  default=False,
                  help='ignore Javascript roots')

parser.add_option("-n", '--node-name-as-root', dest='node_roots',
                  metavar='CLASS_NAME',
                  help='treat nodes with this class name as extra roots')

options, args = parser.parse_args()

if len(args) != 2:
  sys.stderr.write('Expected two arguments.\n')
  exit(0)


# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))

# print an edge description
def print_edge (ga, x, y):
  def print_edge_label (l):
    if len(l) == 2:
      l = l[0]
    sys.stdout.write(l)

  sys.stdout.write('--[')
  lbls = ga.edgeLabels.get(x, {}).get(y, [])
  if len(lbls) != 0:
    print_edge_label(lbls[0])
    for l in lbls[1:]:
      sys.stdout.write(', ')
      print_edge_label(l)
  sys.stdout.write(']->')


# explain why a root is a root
def explain_root (revg, ga, num_known, roots, root):
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
      print_edge(ga, e, root)
      sys.stdout.write (' {0}\n'.format(root))

# print out the path to an object that has been discovered
def print_path (revg, ga, num_known, roots, x, path):
  for p in path:
    print_node(ga, p[0])
    sys.stdout.write('\n    ')
    print_edge(ga, p[0], p[1])
    sys.stdout.write(' ')
  print_node(ga, x)
  print
  print
  if path == []:
    explain_root(revg, ga, num_known, roots, x)
  else:
    explain_root(revg, ga, num_known, roots, path[0][0])
  print


# look for roots and print out the paths to the given object
def findRoots (revg, ga, num_known, roots, x):
  visited = set([])
  path = []
  anyFound = [False]

  def findRootsDFS (y):
    if y in visited:
      return False
    visited.add(y)

    if y in roots:
      path.reverse()
      print_path(revg, ga, num_known, roots, x, path)
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


def selectRoots(g, ga, res):
  roots = {}

  for x in g.keys():
    if not options.ignore_rc_roots and x in res[0]:
      roots[x] = 'rcRoot'
    elif not options.ignore_js_roots and ga.gcNodes.get(x, False):
      roots[x] = 'gcRoot'
    elif ga.nodeLabels.get(x, '') == options.node_roots:
      roots[x] = 'stopNodeLabel'

  return roots      


####################

file_name = args[0]
target = args[1]

(g, ga, res) = loadGraph (file_name)
roots = selectRoots(g, ga, res)
revg = reverseGraph(g)

# won't work on windows if you are searching for an address that starts with anything besides 0
if target[0] == '0':
  targs = [target]
else:
  # look for objects with a class name prefix, not a particular object
  targs = []
  for x in g.keys():
    if ga.nodeLabels.get(x, '')[0:len(target)] == target:
      targs.append(x)
  if targs == []:
    sys.stdout.write('Guessing that argument ' + target + ' is an address.\n')
    targs = [target]

for a in targs:
  if a in g:
    findRoots(revg, ga, res[0], roots, a)
  else:
    sys.stderr.write('{0} is not in the graph.\n'.format(a))


