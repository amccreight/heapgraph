#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple


# Turn a map from strings to count into a count + string pair.
def displayifyMap(baseName, m, maxItems):
  s = baseName + ": "
  count = 0
  numItems = 0
  ellipsed = False

  for stringType, c in sorted(m.items(), reverse=True, key=lambda (a,b): b):
    if numItems < maxItems:
      s += "{} {}, ".format(c, stringType)
    elif not ellipsed:
      s += "..."
      ellipsed = True
    count += c
    numItems += 1

  return (count, s)



nodePatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
edgePatt = re.compile ('> ((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
weakMapEntryPatt = re.compile ('WeakMapEntry map=([a-zA-Z0-9]+|\(nil\)) key=([a-zA-Z0-9]+|\(nil\)) keyDelegate=([a-zA-Z0-9]+|\(nil\)) value=([a-zA-Z0-9]+)\r?$')

def parseRoots (f):
  for l in f:
    if l[:10] == '==========':
      break


def parseGraph (f):
  currNode = None
  currNames = []
  scopeFunctions = {}

  functionNames = {}
  functionScripts = {}
  scriptURLs = {}

  inScope = False
  inFunction = False
  strings = {}
  scopeNames = {}

  for l in f:
    em = edgePatt.match(l)
    if em:
      assert(currNode != None)
      edge = em.group(1)
      lbl = em.group(3)
      if not inScope and not inFunction:
        continue
      if inFunction:
        if lbl != "script":
          continue
        functionScripts[currNode] = edge
        continue
      if lbl == "scope enclosing":
        continue
      if lbl == "scope canonical function":
        scopeFunctions[currNode] = edge
        continue
      if lbl == "scope name":
        name = strings.get(edge)
        if not name:
          print "unknown string"
          exit(-1)
        currNames.append(name)
      elif lbl == "scope env shape":
        continue
      else:
        print 'Error: Unknown scope edge', lbl
        exit(-1)
      continue
    nm = nodePatt.match(l)
    if nm:
      if inScope:
        currNames.sort()
        currNames = ', '.join(currNames)
        scopeNames[currNames] = scopeNames.setdefault(currNames, 0) + 1
      inScope = False
      inFunction = False
      currNode = nm.group(1)
      currNames = []
      lbl = nm.group(3)
      if lbl.startswith("string <"):
        lbl = lbl.split(">")[1].lstrip()
        strings[currNode] = lbl
        continue
      if lbl.startswith("scope"):
        inScope = True
        if len(lbl) >= 6: # "scope "
          lbl = lbl[6:]
        # What to do with the current scope kind?
        continue
      if lbl.startswith("Function"):
        inFunction = True
        # For a Function, could retrieve the script name from the script field.
        if len(lbl) >= 9: # "Function "
          lbl = lbl[9:]
        functionNames[currNode] = lbl
      elif lbl.startswith("script"):
        if len(lbl) >= 7: # "script "
          lbl = lbl[7:]
        # Remove the line number
        lbl = lbl.rsplit(":", 1)[0]
        scriptURLs[currNode] = lbl
    elif l[0] == '#':
      # Skip over comments.
      continue
    else:
      print 'Error: Unknown line:', l[:-1]

  counts = {}
  for k, v in scopeFunctions.iteritems():
    script = scriptURLs.get(functionScripts.get(v, "UNKNOWN"), "UNKNOWN")
    if script == "resource://gre/modules/ReaderMode.jsm":
      print k
    #counts[script] = counts.setdefault(script, 0) + 1

  #for k, v in counts.iteritems():
  #  print k, v


  #displayStuff = []
  #displayStuff.append(displayifyMap("scripts", counts, 20))

  #for _, s in sorted(displayStuff, reverse=True, key=lambda (a,b): a):
  #  print s



  exit(0)
  other = 0
  for k, v in sorted(scopeNames.iteritems(), reverse=True, key=lambda (a,b): a):
    if v < 1:
      other += v
      continue
    print k, v

  if other > 0:
    print "Other:", other


def parseGCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  parseRoots(f)

  parseGraph(f)
  f.close()


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseGCEdgeFile(sys.argv[1])


