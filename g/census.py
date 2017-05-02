#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import re
from collections import namedtuple


####
####  Log parsing
####

nodePatt = re.compile ('((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
edgePatt = re.compile ('> ((?:0x)?[a-fA-F0-9]+) (?:(B|G|W) )?([^\r\n]*)\r?$')
weakMapEntryPatt = re.compile ('WeakMapEntry map=([a-zA-Z0-9]+|\(nil\)) key=([a-zA-Z0-9]+|\(nil\)) keyDelegate=([a-zA-Z0-9]+|\(nil\)) value=([a-zA-Z0-9]+)\r?$')

# A bit of a hack. I'm not sure how up to date this is.
def switchToGreyRoots(l):
  return l == "DOM expando object" or l.startswith("XPCWrappedNative") or \
      l.startswith("XPCVariant") or l.startswith("nsXPCWrappedJS")

def parseRoots (f):
  roots = set([])
  rootLabels = {}
  blackRoot = True;

  prev = None

  for l in f:
    nm = nodePatt.match(l)
    if nm:
      addr = nm.group(1)
      color = nm.group(2)
      lbl = nm.group(3)

      if blackRoot and switchToGreyRoots(lbl):
        blackRoot = False

      # Don't overwrite an existing root, to avoid replacing a black root with a gray root.
      if not addr in roots:
        roots.add(addr)
        rootLabels[lbl] = rootLabels.setdefault(lbl, 0) + 1
    else:
      wmm = weakMapEntryPatt.match(l)
      if wmm:
        # Don't do anything with weak map entries for now.
        continue
      elif l[:10] == '==========':
        break
      elif l[0] == '#':
        # Skip over comments.
        continue
      else:
        print "Error: unknown line ", l
        exit(-1)

  #for r, count in rootLabels.iteritems():
  #  print count, "\t\t", r

  return rootLabels


def parseGraph (f):
  currNode = None

  # Could save more detail for most of these.
  string = {}
  symbol = 0
  jitcode = 0
  function = 0
  Object = 0
  shape = 0
  baseShape = 0
  script = 0
  lazyScript = 0
  objectGroup = 0
  invalid = 0
  array = 0
  call = 0
  other = 0

  for l in f:
    e = edgePatt.match(l)
    if e:
      # Ignore edges
      assert(currNode != None)
      continue
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = nm.group(1)
        nodeColor = nm.group(2)
        lbl = nm.group(3)
        if lbl.startswith("string <"):
          lbl = lbl.split("<")[1].split(":")[0]
          string[lbl] = string.setdefault(lbl, 0) + 1
        elif lbl.startswith("symbol "):
          symbol += 1
        elif lbl == "jitcode":
          jitcode += 1
        elif lbl == "shape":
          shape += 1
        elif lbl == "base_shape":
          baseShape += 1
        elif lbl == "lazyscript":
          lazyScript += 1
        elif lbl == "object_group":
          objectGroup += 1
        elif lbl == "INVALID":
          invalid += 1
        elif lbl == "Array <no private>":
          array += 1
        elif lbl == "Call <no private>":
          call += 1
        elif lbl.startswith("Function"):
          function += 1
        elif lbl.startswith("Object"):
          Object += 1
        elif lbl.startswith("script"):
          script += 1
        else:
          other += 1
      elif l[0] == '#':
        # Skip over comments.
        continue
      else:
        print 'Error: Unknown line:', l[:-1]

  displayStuff = []

  s = "strings: "
  c = 0
  for stringType, count in sorted(string.items(), reverse=True, key=lambda (a,b): b):
    s += "{} {}, ".format(count, stringType)
    c += count
  displayStuff.append((c, s))

  displayStuff.append((symbol, "symbols: {}".format(symbol)))
  displayStuff.append((jitcode, "jitcodes: {}".format(jitcode)))
  displayStuff.append((function, "functions: {}".format(function)))
  displayStuff.append((Object, "objects: {}".format(Object)))
  displayStuff.append((shape, "shapes: {}".format(shape)))
  displayStuff.append((baseShape, "base shapes: {}".format(baseShape)))
  displayStuff.append((script, "scripts: {}".format(script)))
  displayStuff.append((lazyScript, "lazy script: {}".format(lazyScript)))
  displayStuff.append((objectGroup, "object groups: {}".format(objectGroup)))
  displayStuff.append((invalid, "INVALIDs: {}".format(invalid)))
  displayStuff.append((array, "arrays: {}".format(array)))
  displayStuff.append((call, "calls: {}".format(call)))
  displayStuff.append((other, "other: {}".format(other)))

  for _, s in sorted(displayStuff, reverse=True, key=lambda (a,b): a):
    print s



def parseGCEdgeFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  rootLabels = parseRoots(f)

  parseGraph(f)
  f.close()


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseGCEdgeFile(sys.argv[1])


