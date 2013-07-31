#!/usr/bin/python

import sys
import re
from collections import namedtuple

#
# This script analyzes the strings in a GC dump.
#

stringPatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G) string )<length ([0-9]+)(?: \(truncated\))?> ([^\r\n]*)\r?$')
oldStringPatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G) string )([^\r\n]*)\r?$')


# What about substrings?  They look like this:

#0x55ce0f60 W substring 00:08:9f:0c:9f:b8
#> 0x55ce0300 W base


# Also, ropes, which look like this:
# 0x444691a0 B string <rope: length 13>
# > 0x444822a0 B left child
# > 0x44435920 B right child

def analyzeStrings(strings):
  metrics = {}

  for (l, s), count in strings.iteritems():
    # i is the metric of interest
    i = count * l
    metrics.setdefault(i, []).append(s)

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
    for s in x[1]:
      print "{} :: {} x '{}'".format(x[0], x[0]/len(s), s)


#    if len(x[1]) <= 10:
#      print x[1]
#    else:
#      print 'TOO MANY'


# This parses a file f and produces a dict mapping strings to the number of times
# the strings occur.
def parseGCLogInner(f):
  strings = {}
  for l in f:
    stringMatch = stringPatt.match(l)
    if stringMatch:
      # 1 is the address
      # 2 is the color
      # 3 is the length
      # 4 is the string itself
      desc = (int(stringMatch.group(3)), stringMatch.group(4))
      strings[desc] = strings.get(desc, 0) + 1
    else:
      stringMatch = oldStringPatt.match(l)
      if stringMatch:
        s = stringMatch.group(3)
        desc = (len(s), s)
        strings[desc] = strings.get(desc, 0) + 1

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

