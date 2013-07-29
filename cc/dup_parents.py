#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

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
