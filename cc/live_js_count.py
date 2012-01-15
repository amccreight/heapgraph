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
        if nlbl.startswith("nsDocument"):
#        if nlbl.startswith("nsGenericElement"):
#        if nlbl.startswith("nsGenericElement") or nlbl.startswith("nsDocument"):
          assert(dst in ga.gcNodes)
          assert(not ga.gcNodes[dst])
          live.add(dst)
          continue
#        print "Unexpected JS holder label ", src, ":", nlbl

  print "Found", len(live), "JS objects held directly by live C++."

  return live


def flood_from (g, ga, s):
  marked = set([])

  def flood_from_rec (x):
    for y in g[x]:
      if not y in marked and y in ga.gcNodes and (not ga.gcNodes[y]):
        marked.add(y)
        flood_from_rec(y)

  for x in s:
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

live = live_js(g, ga)

livejs = flood_from(g, ga, live)

unlive(g, ga, livejs)
