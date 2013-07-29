#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Analyze C++ objects that hold references to JS objects.

import sys
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser


# Command line arguments

usage = "usage: %prog [options] file_name\n\
  file_name is the name of the cycle collector graph file"
parser = OptionParser(usage=usage)

parser.add_option("-i", '--individual', dest='individual', action='store_true',
                  default=False,
                  help='Print out address and label of individual JS holders.')

parser.add_option("-c", '--combine-labels', dest='canonize', action='store_true',
                  default=False,
                  help='When aggregating, combine similar labels, like all XUL nodes.')

parser.add_option('-m', '--min',
                  action='store', dest='min_display', type='int',
                  default=0,
                  help='When aggregating, only print labels with at least this many occurrences.')

options, args = parser.parse_args()

if len(args) != 1:
  print 'Expected one argument.'
  exit(0)



# should move this canonize thing into a library

starts_with = set (['nsGenericElement (XUL)', 'nsGenericElement (xhtml)', 'nsGenericElement (XBL)', \
                      'nsNodeInfo (XUL)', 'nsNodeInfo (xhtml)', 'nsNodeInfo (XBL)', \
                      'nsXPCWrappedJS', 'JS Object (XULElement)', \
                      'nsDocument normal (xhtml)', \
                      'nsDocument (xhtml)', \
                      'XPCWrappedNative', 'nsJSScriptTimeoutHandler', \
                      'nsGenericElement (SVG)',])


def canonize_label(l):
  if not options.canonize:
    return l
  for s in starts_with:
    if l.startswith(s):
      return s
  return l

# end canonize



def find_js_holders(g, ga):
  if not options.individual:
    js_holders = {}
  else:
    js_holders = set([])

  for src, dsts in g.iteritems():
    if src in ga.rcNodes:
      for d in dsts:
        if d in ga.gcNodes:
          name = canonize_label(ga.nodeLabels[src])
          if not options.individual:
            js_holders[name] = js_holders.get(name, 0) + 1
          else:
            js_holders.add(src)
          break

  return js_holders


def load_graph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  sys.stderr.flush()
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  sys.stderr.write ('Done loading graph.\n')

  return (g, ga)



(g, ga) = load_graph (args[0])
holders = find_js_holders(g, ga)

if not options.individual:
  for name, count in holders.iteritems():
    if count >= options.min_display:
      sys.stdout.write('%(num)8d %(label)s\n' % {'num':count, 'label':name})
else:
  for addr in holders:
    print ga.nodeLabels[addr], '\t', addr




