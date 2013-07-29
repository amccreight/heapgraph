#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser


# Analyze the set of JS objects held live by preserved wrappers.


def load_graph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  sys.stderr.write('Done loading graph.\n')

  return (g, ga)


# Return a set of JS objects that are held by live C++ objects.  For
# now, just a hack that looks for objects that have only a single
# field "Preserved wrapper".
def live_js(g, ga):
  live = set([])
  holders = set([])
  dummy = [""]

  for src, edges in g.iteritems():
    if src in ga.rcNodes:
      if len(edges) != 1:
        continue
      for dst, n in edges.iteritems():
        if n != 1:
          continue
        if ga.edgeLabels[src].get(dst, dummy)[0] != "Preserved wrapper":
          continue
        nlbl = ga.nodeLabels[src]
        if not (nlbl.startswith("nsGenericElement") or \
                nlbl.startswith("nsDocument") or \
                nlbl.startswith("nsGenericDOMDataNode")):
          sys.stderr.write ("Unexpected JS holder label " + src + ": " + nlbl + "\n")
        else:
          assert(dst in ga.gcNodes)
          assert(not ga.gcNodes[dst])
          live.add(dst)
          holders.add(src)

  print "Found", len(live), "JS objects held directly by live C++."

  return (holders, live)


# even cruder than live_js: just assume that everything of a
# particular class is live, and thus JS it holds is live.
def class_based_live_js(g, ga):
  live = set([])
  holders = set([])
  class_name = "JSContext"

  for src, edges in g.iteritems():
    if src in ga.rcNodes:
      if ga.nodeLabels[src].startswith(class_name):
        holders.add(src)
        for dst, n in edges.iteritems():
          if dst in ga.gcNodes and not ga.gcNodes[dst]:
            live.add(dst)

  print "Found", len(live), "JS objects held directly by class", class_name

  return (holders, live)


def flood_from (g, ga, holders, live):
  marked = set([])

  def flood_from_rec (x):
    for y in g[x]:
      if not y in marked and y in ga.gcNodes and (not ga.gcNodes[y]):
        marked.add(y)
        flood_from_rec(y)
      if y in ga.rcNodes and not y in holders:
        print "reached: ", ga.nodeLabels[y], "\t", y

  for x in live:
    assert(x in ga.gcNodes)
    assert(not ga.gcNodes[x])
    if not x in marked:
      marked.add(x)
      flood_from_rec(x)

  print "Found", len(marked), "JS objects held directly or indirectly by live C++."

  return marked


def unlive (g, ga, live):
  unlive = 0
  for x in g:
    if not x in live and x in ga.gcNodes:
      unlive += 1
  print "Found", unlive, "other JS objects."




####################

file_name = sys.argv[1]

(g, ga) = load_graph (file_name)

(holders, live) = live_js(g, ga)

livejs = flood_from(g, ga, holders, live)

unlive(g, ga, livejs)
