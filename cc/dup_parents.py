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

# associate each DOM node with its uppermost parent.


import sys
import re
import parse_cc_graph


nodePatt = re.compile ('([a-zA-Z0-9]+) \[(?:rc=[0-9]+|gc(?:.marked)?)\] (.*)$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) (.*)$')

def parseGraph (f):
  numEdges = 0

  currNode = None
  numDups = {}
  firstNode = True

  for l in f:
    if l[0] == '>':
      numEdges += 1
      e = edgePatt.match(l)
      edgeLabel = e.group(2)
      if edgeLabel == 'parent':
        if foundParent:
          currDups += 1
        else:
          foundParent = True
    else:
      nm = nodePatt.match(l)
      if nm:
        if (not firstNode):
          numDups[currDups] = numDups.get(currDups, 0) + 1
          if currDups > 0:
            print currDups, currNode, currLabel
        currNode = nm.group(1)
        currLabel = nm.group(2)
        firstNode = False
        foundParent = False
        currDups = 0

      elif l == '==========\n':
        if currDups > 0:
            print currDups, currNode, currLabel
        numDups[currDups] = numDups.get(currDups, 0) + 1
        break
      else:
        print 'Error: Unknown line:', l[:-1]

  f.close()

  print numDups


def parseCCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  pg = parseGraph(f)
  f.close()


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseCCEdgeFile(sys.argv[1])
