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

# CCC: Cycle collector checker.


# Implementation of the cycle collector algorithm in Python, along
# with checker to compare the results to those reported by Fx.
#
# Same basic idea as Bacon-Rajan 01, but implemented slightly
# differently, as we just examine the entire CC heap.

def computeInternalCounts (g, ga):
  ics = {}
  
  for src, edges in g.iteritems():
    for dst, count in edges.iteritems():
      if dst in ga.rcNodes:
        ics[dst] = ics.get(dst, 0) + count

  return ics

# A refcounted node is a root if its ref count > its computed internal count.
def computeRefCountedRoots (ga, ics):
  roots = set([])

  for x, rc in ga.rcNodes.iteritems():
    ic = ics.get(x, 0)
    if rc > ic:
      roots.add(x)
    elif ic > rc:
      print 'Error: computed internal count of', x, 'greater than supplied reference count.'
      exit(-1)

  return roots

# Compute the set of live objects reachable from the roots.
def reachableFromRoots (g, ga, rcRoots):
  live = set([])

  def floodLive (x):
    live.add(x)
    assert(x in g)
    for y in g[x].keys():
      if not y in live:
        floodLive(y)

  # flood from ref counted roots
  for x in rcRoots:
    if not x in live:
      floodLive(x)

  # flood from garbage collected roots
  for x, marked in ga.gcNodes.iteritems():
    if marked and not x in live:
      floodLive(x)

  return live


def cycleCollect (g, ga):
  # compute results
  ics = computeInternalCounts(g, ga)
  rcRoots = computeRefCountedRoots (ga, ics)
  live = reachableFromRoots (g, ga, rcRoots)

  # produce results in the same format as the Fx CC
  knownEdges = {}
  for x in rcRoots:
    knownEdges[x] = ics.get(x, 0)
  garbage = set(g.keys()) - live

  return (knownEdges, garbage)


def graphRange (g):
  r = set([])
  for edges in g.values():
    r |= set(edges.keys())
  return r


# some basic coherence checks on the graph
def checkGraph (g, ga):
  rcs = set(ga.rcNodes.keys())
  gcs = set(ga.gcNodes.keys())
  # no nodes are both RC and GC
  assert(rcs & gcs == set([]))

  # all ref counts are non-zero positive integers
  for v in ga.rcNodes.values():
    assert (v > 0)

  # all GC nodes map to either True or False
  assert(set(ga.gcNodes.values()) - set([True, False]) == set([]))

  gd = set(g.keys())

  # everything in the graph range is in the domain
  if graphRange(g) - gd != set([]):
    print '\nError: nodes in graph range but not domain:', graphRange(g) - gd
    exit(-1)
  # all nodes are either ref counted or GCed
  assert(gd == rcs | gcs)

  # I don't bother checking anything related to labels here
  

def checkResults (g, ga, (knownEdgesFx, garbageFx), (knownEdgesPy, garbagePy)):
  resultsOk = True

  # check that calculated garbage is identical
  if garbageFx != garbagePy:
    print
    resultsOk = False
    s1 = garbageFx - garbagePy
    for x in s1:
      print '  Error:', x, 'was reported as garbage by the Fx CC, but not the Python CC.'
      foundAnyBad = True
    s2 = garbagePy - garbageFx
    for x in s2:
      print '  Error:', x, 'was reported as garbage by the Python CC, but not the Fx CC.'
      foundAnyBad = True
    assert(s1 != set([]) or s2 != set([]))

  # check that roots and known edges match up
  if knownEdgesFx != knownEdgesPy:
    if resultsOk:
      print
    resultsOk = False
    for x in g.keys():
      if x in knownEdgesFx:
        if not x in knownEdgesPy:
          print '  Error:', x, 'had known edges reported, but Python did not think it was a root.'
        else:
          if knownEdgesFx[x] != knownEdgesPy[x]:
            sys.stdout.write ('  Error: Fx and Python disagree on internal count for {0} (computed {1}, reported {2})\n'.format\
                                (x, knownEdgesPy[x], knownEdgesFx[x]))            
      else:
        if x in knownEdgesPy:
          print '  Error:', x, 'in computed root set, but not Fx-reported root set.'

  return resultsOk


def parseAndCheckResults(fname):
  print 'Checking ' + fname + '.',

  print 'Parsing.',
  sys.stdout.flush()
  pef = parse_cc_graph.parseCCEdgeFile(fname)
  g = pef[0]
  ga = pef[1]
  resFx = pef[2]

  print 'Checking graph.',
  sys.stdout.flush()
  checkGraph(g, ga)

  print 'Running PyCC.',
  sys.stdout.flush()
  resPy = cycleCollect(g, ga)

  print 'Comparing results.',
  sys.stdout.flush()
  ok = checkResults (g, ga, resFx, resPy)
  if ok:
    print 'Ok.'
  else:
    print 'Error.'
    exit(-1)

  return ok


####################

if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()


allOk = True
for fname in sys.argv[1:]:
  allOk &= parseAndCheckResults(fname)

if allOk:
  print 'All files were okay.'
else:
  print 'Error: One or more files failed checking.'
