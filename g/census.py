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
  inFunction = False

  string = {}
  symbol = 0
  jitcode = 0
  function = {}
  functionScripts = {}
  Object = 0
  shape = 0
  baseShape = 0
  script = {}
  scriptURLs = {}
  lazyScript = 0
  objectGroup = 0
  invalid = 0
  array = 0
  call = 0
  other = 0
  regexp = 0
  scope = {}

  for l in f:
    em = edgePatt.match(l)
    if em:
      assert(currNode != None)
      if inFunction and em.group(3) == "script":
        functionScripts[currNode] = em.group(1)
      continue
    else:
      inFunction = False
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
        elif lbl == "reg_exp_shared":
          regexp += 1
        elif lbl.startswith("scope"):
          if len(lbl) >= 6: # "scope "
            lbl = lbl[6:]
          scope[lbl] = scope.setdefault(lbl, 0) + 1
        elif lbl == "INVALID":
          invalid += 1
        elif lbl == "Array <no private>":
          array += 1
        elif lbl == "Call <no private>":
          call += 1
        elif lbl.startswith("Function"):
          inFunction = True
          # For a Function, could retrieve the script name from the script field.
          if len(lbl) >= 9: # "Function "
            lbl = lbl[9:]
          function.setdefault(lbl, []).append(currNode)
        elif lbl.startswith("Object"):
          Object += 1
        elif lbl.startswith("script"):
          if len(lbl) >= 7: # "script "
            lbl = lbl[7:]
          # Remove the line number
          lbl = lbl.rsplit(":", 1)[0]
          script[lbl] = script.setdefault(lbl, 0) + 1
          scriptURLs[currNode] = lbl
        else:
          other += 1
      elif l[0] == '#':
        # Skip over comments.
        continue
      else:
        print 'Error: Unknown line:', l[:-1]

  scriptyFunctions = {}
  for (f, faddrs) in function.iteritems():
    for fa in faddrs:
      scriptName = scriptURLs.get(functionScripts.get(fa, "NONE"), "???")
      key = f
      if scriptName != "???":
        key = key + " " + scriptName
      scriptyFunctions[key] = scriptyFunctions.setdefault(key, 0) + 1


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


  displayStuff = []

  displayStuff.append(displayifyMap("strings", string, 5))
  displayStuff.append(displayifyMap("functions", scriptyFunctions, 40))
  displayStuff.append(displayifyMap("scripts", script, 10))
  displayStuff.append(displayifyMap("scopes", scope, 10))

  displayStuff.append((symbol, "symbols: {}".format(symbol)))
  displayStuff.append((jitcode, "jitcodes: {}".format(jitcode)))
  displayStuff.append((Object, "objects: {}".format(Object)))
  displayStuff.append((shape, "shapes: {}".format(shape)))
  displayStuff.append((baseShape, "base shapes: {}".format(baseShape)))
  displayStuff.append((regexp, "regexps: {}".format(regexp)))
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


