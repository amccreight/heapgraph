#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser


def load_graph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  sys.stderr.write ('Converting to single graph. ') 
  g = parse_cc_graph.toSinglegraph(g)
  sys.stderr.write('Done loading graph.\n')

  return (g, ga, res)


####################

file_name = sys.argv[1]

(g, ga, res) = load_graph (file_name)
