#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Count how many edges nodes of a certain class have.  I'm trying
# baking this directly into the parser in hopes of improving speed.


import sys
import re
from collections import namedtuple


####
####  Log parsing
####

nodePatt = re.compile ('([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] (.*)$')


def scooper (f, name):
  counts = {}
  currNode = None

  for l in f:
    if currNode != None:
      if l[0] == '>':
        counts[currNode] = counts[currNode] + 1
        continue
      else:
        currNode = None
    nm = nodePatt.match(l)
    if nm:
      if nm.group(3) == name:
        currNode = nm.group(1)
        counts[currNode] = 0
    elif l == '==========\n':
      break

  buckets = {}

  for l, k in counts.iteritems():
    if k > 1:
      print '%(num)8d %(label)s' % {'num':k, 'label':l}
      buckets[k] = buckets.get(k, 0) + 1

  print buckets


try:
  f = open(sys.argv[1], 'r')
except:
  print 'Error opening file', sys.argv[1]
  exit(-1)

scooper(f, sys.argv[2])

