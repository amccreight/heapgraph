#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple
import node_parse_cc_graph
import argparse


# Print out high level information about a CC log.


parser = argparse.ArgumentParser(description='Produce a high-level summary about a cycle collector log.')

parser.add_argument('file_name',
                    help='cycle collector graph file name')

parser.add_argument('--live', dest='live', action='store_true',
                    default=False,
                    help='Analyze live objects. Default if --dead is not selected.')

parser.add_argument('--dead', dest='dead', action='store_true',
                    default=False,
                    help='Analyze dead objects. Not by default.')

parser.add_argument('--min-times', '-mt', dest='min_times', type=int,
                    default=5,
                    help='Only show objects that appear at least this many times. Default is 5.')

parser.add_argument('--num-show-freq', dest='num_to_show', type=int,
                    default=5,
                    help='Only show this many of the most frequent objects. Default is 5.')

parser.add_argument('--min-rc', dest='min_rc', type=int,
                    default=0,
                    help='When analyzing ref counts, only show objects with at least this many. Default is 0.')

parser.add_argument('--num-show-rc', dest='num_rc_to_show', type=int,
                    default=5,
                    help='Only show this many of the objects with high ref counts. Default is 5.')


# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))


obj_patt = re.compile ('(JS Object \([^\)]+\)) \(global=[0-9a-fA-F]*\)')

starts_with = set (['nsGenericElement (XUL)', \
                    'nsGenericElement (xhtml) span ', \
                    'nsGenericElement (xhtml) a ', \
                    'nsGenericElement (xhtml) input ', \
                    'nsGenericElement (XBL)', \
                    'nsGenericDOMDataNode', \
                    'nsNodeInfo (XUL)', 'nsNodeInfo (xhtml)', 'nsNodeInfo (XBL)', \
                    'XPCWrappedNative', \
                    'nsXPCWrappedJS', \
                    'nsDocument', \
                  ])


# Skip the merging by uncommenting the next line.
#starts_with = set([])


def canonize_label(l):
#  lm = obj_patt.match(l)
#  if lm:
#    return lm.group(1)
  if l.startswith('JS Object'):
    if l.startswith('JS Object (Function'):
      return 'JS Object (Function)'
    else:
      return 'JS Object (other)'
  else:
    for s in starts_with:
      if l.startswith(s):
        return s

  return l

# This method takes a map from labels to number of occurences of that label,
# along with the minimum number frequency we care about, and returns the inverse
# of the map (for the parts of the input map whose range is at least |min_times|)
# along with an ordered list of the domain of the output map.
def invert_counts_map(counts_map, min_times):
  inv_counts_map = {}
  for l, n in counts_map.iteritems():
    if n < min_times:
      continue
    inv_counts_map.setdefault(n, []).append(l)

  inv_domain = sorted(list(inv_counts_map))
  inv_domain.reverse()

  return [inv_counts_map, inv_domain]


def print_inv_counts_map(inv_counts_map, inv_domain, num_to_show):
  num_printed = 0
  for count in inv_domain:
    if num_printed == num_to_show:
      break
    for l in inv_counts_map[count]:
      if num_printed == num_to_show:
        break
      num_printed += 1
      print '%(num)8d %(label)s' % {'num':count, 'label':l}


def analyze_nodes(args, nodes, ga, garb):
  # First, figure out which nodes to look at.
  if args.dead:
    if args.live:
      nodes_of_interest = nodes
    else:
      nodes_of_interest = garb
  else:
    nodes_of_interest = nodes - garb


  # Carry out a first pass to gather basic data.
  nls = {}
  ref_count_map = {}
  js_fn_counts = {}
  for n in nodes_of_interest:
    # Counts by label
    l = ga.nodeLabels[n]

    if l.startswith('JS Object (Function'):
      fn_lbl = l[19:]
      if fn_lbl == ')':
        fn_lbl = '(no name in log)'
      else:
        fn_lbl = fn_lbl[3:-1]
      js_fn_counts[fn_lbl] = js_fn_counts.get(fn_lbl, 0) + 1

    l = canonize_label(l)
    nls[l] = nls.get(l, 0) + 1

    # Ref count info
    if n in ga.rcNodes:
      rc = ga.rcNodes[n]
      if rc < args.min_rc:
        continue
      ref_count_map.setdefault(rc, []).append(n)


  # Analyze which counts are most frequent.
  [count_map, counts] = invert_counts_map(nls, args.min_times)
  [js_fn_map, js_fn_map_dom] = invert_counts_map(js_fn_counts, args.min_times)

  ref_counts = sorted(list(ref_count_map))
  ref_counts.reverse()


  # Print results.
  print 'Object frequency.',
  print 'Showing no more than', args.num_to_show, 'classes of objects, with at least', args.min_times, 'objects each.'
  print_inv_counts_map(count_map, counts, args.num_to_show)
  print

  print 'JS function object frequency.',
  print 'Showing no more than', args.num_to_show, 'JS function objects, with at least', args.min_times, 'objects each.'
  print_inv_counts_map(js_fn_map, js_fn_map_dom, args.num_to_show)
  print

  [js_fn_map, js_fn_map_dom] = invert_counts_map(js_fn_counts, args.min_times)

  print 'Objects with highest ref counts.',
  print 'Showing no more than', args.num_rc_to_show, 'objects, with ref count of at least', args.min_rc

  num_printed = 0
  for n in ref_counts:
    if num_printed == args.num_rc_to_show:
      break
    for x in ref_count_map[n]:
      if num_printed == args.num_rc_to_show:
        break
      num_printed += 1
      print '  rc=%(num)d %(addr)s %(label)s' % {'num':n, 'addr':x, 'label':ga.nodeLabels[x]}



#######

printParsingStatus = False

def loadGraph(fname):
  if printParsingStatus:
    sys.stdout.write('Parsing {0}. '.format(fname))
    sys.stdout.flush()
  (g, ga, res) = node_parse_cc_graph.parseCCEdgeFile(fname)
  if printParsingStatus:
    sys.stdout.write('Done loading graph.\n')

  return (g, ga, res)


####################


def cycleCollectorCensus():
  args = parser.parse_args()

  (g, ga, res) = loadGraph(args.file_name)
  (ke, garb) = res

  analyze_nodes(args, g, ga, garb)



if __name__ == "__main__":
  cycleCollectorCensus()


