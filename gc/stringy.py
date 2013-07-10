#!/usr/bin/python

import sys
import re
from collections import namedtuple

#
# This script analyzes the strings in a GC dump.
#

# will need to update this with lengths.
stringPatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G) string )([^\r\n]*)\r?$')


# What about substrings?  They look like this:

#0x55ce0f60 W substring 00:08:9f:0c:9f:b8
#> 0x55ce0300 W base


def analyzeStrings(strings):
  metrics = {}

  for s, count in strings.iteritems():
    # i is the metric of interest
    i = count * len(s)
    if not i in metrics:
      metrics[i] = []
    metrics[i].append(s)

  # probably a better way to listify here...
  l = []
  for c, s in metrics.iteritems():
    l.append((c, s))
  l = sorted(l, reverse=True)


  print 'total chars :: strings'
  howMany = 20
  for x in l:
    if howMany == 0:
      break
    howMany -= 1
    print x[0], '::',
    if len(x[1]) <= 10:
      print x[1]
    else:
      print 'TOO MANY'


# This parses a file f and produces a dict mapping strings to the number of times
# the strings occur.
def parseGCLogInner(f):
  strings = {}
  for l in f:
    stringMatch = stringPatt.match(l)
    if stringMatch:
      # 1 is the address
      # 2 is the color
      # 3 is the string itself
      s = stringMatch.group(3)
      strings[s] = strings.get(s, 0) + 1
  return strings

def parseGCLog (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  strings = parseGCLogInner(f)
  f.close()
  analyzeStrings(strings)


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseGCLog(sys.argv[1])

