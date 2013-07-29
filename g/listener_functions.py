#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


# Find functions used as listeners.

import sys
import parse_gc_graph


def loadListeners(f, listenerRoots):
    numGrayListeners = 0
    numBlackListeners = 0
    labels = {}

    for l in f:
        nm = parse_gc_graph.nodePatt.match(l)
        if nm:
            if nm.group(1) in listenerRoots:
                nodeColor = nm.group(2)
                if nodeColor == 'G':
                    numGrayListeners += 1
                else:
                    assert(nodeColor == 'B')
                    numBlackListeners += 1
                lbl = nm.group(3)
                labels[lbl] = labels.setdefault(lbl, 0) + 1

    print 'Found {} gray listeners and {} black listeners'.format(numGrayListeners, numBlackListeners)

    for l, count in labels.iteritems():
        if count > 100:
            print '{:5} {}'.format(count, l)





def findListeners (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  # Load the roots.
  [roots, rootLabels] = parse_gc_graph.parseRoots(f)

  listenerRoots = set([])
  for r, l in rootLabels.iteritems():
      if l.startswith('nsXPCWrappedJS[nsIDOMEventListener'):
          listenerRoots.add(r)
  roots = None
  rootLabels = None


  # Load the nodes themselves.
  loadListeners(f, listenerRoots)

  # whatever
  f.close()

  #print listenerRoots





if len(sys.argv) < 2:
    print 'Not enough arguments.'
    exit()

findListeners(sys.argv[1])
