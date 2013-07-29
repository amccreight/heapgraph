#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from optparse import OptionParser
from collections import namedtuple
import parse_cc_graph

# CCC: Cycle collector checker.
#
# Implementation of the cycle collector algorithm in Python, along
# comparison of those results to those reported by Fx.  There are also
# a few basic well-formedness checks that are done.
#
# Same basic idea as Bacon-Rajan 01, but implemented slightly
# differently, as we examine the entire CC heap:
#
#   - Compute the number of edges in the graph pointing to each node
#     (the 'internal counts').
#
#   - Compute the set of ref-counted roots, which are ref-counted
#     objects where the ref count is greater than the internal count.
#
#   - Compute live set of objects reachable from marked GC objects or
#     ref-counted roots.
#
#   - Convert output to the same format as the FX CC.  Any objects in
#     the set of live objects are garbage.


# Arguments: one or more cycle collector edge files, which will be checked in sequence.

usage = "usage: %prog FILE1 FILE2 ... FILEn\n\
  Each FILE is a cycle collector graph file to check."
description = 'Check one or more cycle collector result files for correctness relative to the cycle collector graph.'
parser = OptionParser(description=description, usage=usage)

options, args = parser.parse_args()


# Calculate how many references are accounted for by edges in the graph.
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


# perform cycle collection on the graph
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
  rcs = set(ga.rcNodes.keys())  # RCed nodes
  gcs = set(ga.gcNodes.keys())  # GCed nodes

  # no nodes can be both RC and GC
  if (rcs & gcs) != set([]):
    print 'Some nodes are both ref counted and gced:',
    for x in rcs & gcs:
      print x
    exit(-1)

  # all ref counts must be non-zero positive integers
  for v in ga.rcNodes.values():
    if v <= 0:
      print 'Found a negative or zero ref count.'
      exit(-1)

  # all GC nodes map to either True or False
  assert(set(ga.gcNodes.values()) - set([True, False]) == set([]))

  gd = set(g.keys())

  # everything in the graph range is in the domain
  if graphRange(g) - gd != set([]):
    print '\nError: nodes in graph range but not domain:', graphRange(g) - gd
    exit(-1)
  # all nodes are either ref counted or GCed
  assert(gd == rcs | gcs)

  # Nothing related to labels is checked.


def checkResults (g, ga, (knownEdgesFx, garbageFx), r1Name,
                         (knownEdgesPy, garbagePy), r2Name):
  resultsOk = True

  # check that calculated garbage is identical
  if garbageFx != garbagePy:
    print
    resultsOk = False
    s1 = garbageFx - garbagePy
    for x in s1:
      print '  Error:', x, 'was reported as garbage by ' + r1Name + ' but not ' + r2Name
      foundAnyBad = True
    s2 = garbagePy - garbageFx
    for x in s2:
      print '  Error:', x, 'was reported as garbage by ' + r1Name + ' but not ' + r2Name
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
          print '  Error:', x, 'had known edges reported, but ' + r2Name + ' did not think it was a root.'
        else:
          if knownEdgesFx[x] != knownEdgesPy[x]:
            sys.stdout.write ('  Error: results disagree on internal count for {0} (computed {1}, reported {2})\n'.format\
                                (x, knownEdgesPy[x], knownEdgesFx[x]))
      else:
        if x in knownEdgesPy:
          print '  Error:', x, 'in ' + r2Name + ' root set, but not ' + r1Name + ' root set.'

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
  ok = checkResults (g, ga, resFx, 'Firefox cycle collector',
                            resPy, 'Python cycle collector')
  if ok:
    print 'Ok.'
  else:
    print 'Error.'
    exit(-1)

  return ok


####################


allOk = True
for fname in args:
  allOk &= parseAndCheckResults(fname)

if allOk:
  print 'All files were okay.'
else:
  print 'Error: One or more files failed checking.'
