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
import re
from collections import namedtuple
import parse_cc_graph


def node_string (x, ga):
  if x in ga.rcNodes:
    t = 'rc=' + str(ga.rcNodes[x])
  elif ga.gcNodes[x]:
    t = 'gc.marked'
  else:
    t = 'gc'
  if x in ga.nodeOptLabels:
    optLbl = ' {' + ga.nodeOptLabels[x] + '}'
  else:
    optLbl = ''
  if x in ga.nodeLabels:
    lbl = ' ' + ga.nodeLabels[x]
  else:
    lbl = ''
  return '{0} [{1}]{2}{3}'.format(x, t, optLbl, lbl)


def edge_string (dst, olbl, lbl):
  t = '> ' + dst
  if olbl != None:
    t += ' {' + olbl + '}'
  if lbl != None:
    t += ' ' + lbl
  return t


def print_reverse_graph (g, ga):
  for src, outs in g.iteritems():
    print node_string(src, ga)
    for dst, numEdges in outs.iteritems():
      if (dst, src) in ga.edgeLabels:
        for ll in ga.edgeLabels[(dst, src)]:
          print edge_string (dst, ll[0], ll[1])
        numEdges -= len(ga.edgeLabels[(dst, src)])
      for x in range(numEdges):
        print edge_string (dst, None, None)

if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()


x = parse_cc_graph.parseCCEdgeFile(sys.argv[1])

r = parse_cc_graph.reverseMultigraph(x[0])
#assert(x[0] == parse_cc_graph.reverseMultigraph(r)

print_reverse_graph (r, x[1])




