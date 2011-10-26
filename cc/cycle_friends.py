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

usage = "usage: %prog file_name target\n\
  file_name is the name of the cycle collector graph file\n\
  target is the object to look for"
parser = OptionParser(usage=usage)

options, args = parser.parse_args()

if len(args) != 2:
  print 'Expected two arguments.'
  exit(0)


def reverseGraph (g):
  g2 = {}
  print 'Reversing graph.'
  sys.stdout.flush()
  for src, dsts in g.iteritems():
    for d in dsts:
      g2.setdefault(d, set([])).add(src)
  return g2


def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  #sys.stdout.write ('Converting to single graph. ') 
  #sys.stdout.flush()
  g = parse_cc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga, res)


def reachableFrom (g, garb, x):
  if not x in garb:
    print x, "is not garbage"
    exit -1

  visited = {x:True}
  working = [x]
  s = set([x])

  while [] != working:
    curr = working.pop()

    if not curr in g:
      continue

    for next in g[curr]:
      if not next in visited and next in garb:
        visited[next] = True
        working.append(next)
        s.add(next)

  return s


####################

file_name = args[0]
target = args[1]

(g, ga, res) = loadGraph (file_name)

print
print "Computing forward direction"

# garbage objects reachable from target
forw = reachableFrom(g, res[1], target)

print "Computing backwards direction"

# garbage objects that reach target
revg = reverseGraph(g)
backw = reachableFrom(revg, res[1], target)

# members of garbage cycle including target
print "Cycle members:", 
cyc = list(forw & backw)
cyc.sort()

for i in cyc:
  print i,
print



