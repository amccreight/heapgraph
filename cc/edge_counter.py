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

