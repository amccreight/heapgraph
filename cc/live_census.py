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
import node_parse_cc_graph
from optparse import OptionParser


# print out classes of live objects

# Command line arguments

usage = "usage: %prog file_name\n\
  file_name is the name of the cycle collector graph file"
parser = OptionParser(usage=usage)

options, args = parser.parse_args()

if len(args) != 1:
  print 'Expected one argument.'
  exit(0)


# print a node description
def print_node (ga, x):
  sys.stdout.write ('{0} [{1}]'.format(x, ga.nodeLabels.get(x, '')))


obj_patt = re.compile ('(JS Object \([^\)]+\)) \(global=[0-9a-fA-F]*\)')

#starts_with = set (['nsGenericElement (XUL)', 'nsGenericElement (xhtml)', 'nsGenericElement (XBL)', \
#                      'nsNodeInfo (XUL)', 'nsNodeInfo (xhtml)', 'nsNodeInfo (XBL)', \
#                      'nsXPCWrappedJS', 'JS Object', 'nsDocument', 'XPCWrappedNative'])

starts_with = set (['nsGenericElement (XUL)', \
                      'nsGenericElement (xhtml) span ', \
                      'nsGenericElement (xhtml) a ', \
                      'nsGenericElement (xhtml) input ', \
                      'nsGenericElement (XBL)', \
                      'nsNodeInfo (XUL)', 'nsNodeInfo (xhtml)', 'nsNodeInfo (XBL)', \
                      'nsXPCWrappedJS', 'JS Object', 'nsDocument', 'XPCWrappedNative'])


def canonize_label(l):
#  return l

#  lm = obj_patt.match(l)
#  if lm:
#    return lm.group(1)
  for s in starts_with:
    if l.startswith(s):
      return s
  return l


def analyze_live (nodes, ga, garb):
  nls = {}

  for n in nodes - garb:
    # skipped marked nodes, on the assumption that the CC is decent about avoiding them
    if n in ga.gcNodes and ga.gcNodes[n]:
      continue

    l = ga.nodeLabels[n]
    l = canonize_label(l)
    nls[l] = nls.get(l, 0) + 1

  other = 0
  for l, n in nls.iteritems():
    if n > 0:
      print '%(num)8d %(label)s' % {'num':n, 'label':l}
    else:
      other += n

  print '%(num)8d,other' % {'num':other}

def loadGraph(fname):
  #sys.stdout.write ('Parsing {0}. '.format(fname))
  #sys.stdout.flush()
  (g, ga, res) = node_parse_cc_graph.parseCCEdgeFile(fname)
  #print 'Done loading graph.',

  return (g, ga, res)


####################

file_name = args[0]

(g, ga, res) = loadGraph (file_name)
(ke, garb) = res
analyze_live(g, ga, garb)

