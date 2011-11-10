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
import fast_parse_cc_graph


# which classes (or maybe even specific objects) hold into a particular class of objects?


# print out classes of live objects

# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))


obj_patt = re.compile ('(JS Object \([^\)]+\)) \(global=[0-9a-fA-F]*\)')



def canonicalize_name (n):
  nm = obj_patt.match(n)
  if nm:
    return nm.group(1)
  return n


def get_holders (g, ga, garb, name):
  children = set([])

  for n in g:
    if name == ga.nodeLabels[n]:
      children.add(n)

  print 'Num children found:', len(children)

  parents = {}

  for n, e in g.iteritems():
    overlap = e & children
    if len(overlap) != 0:
      l = canonicalize_name(ga.nodeLabels[n])
      parents[l] = parents.get(l, 0) + len(overlap)

  other = 0
  for l, n in parents.iteritems():
    if n > 0:
      print '%(num)8d %(label)s' % {'num':n, 'label':l}
    else:
      other += n

  if other != 0:
    print '%(num)8d other' % {'num':other}


def loadGraph(fname):
  sys.stderr.write ('Parsing {0}. '.format(fname))
  sys.stderr.flush()
  (g, ga, res) = fast_parse_cc_graph.parseCCEdgeFile(fname)
  sys.stderr.write('Done loading graph.\n')
  sys.stderr.flush()

  return (g, ga, res)


####################

file_name = sys.argv[1]
class_name = sys.argv[2]

(g, ga, res) = loadGraph (file_name)
(ke, garb) = res
get_holders(parse_cc_graph.toSinglegraph(g), ga, garb, class_name)

