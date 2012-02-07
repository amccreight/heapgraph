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


# union find with path compression and union by rank

def findi (m, x):
  if not x in m:
    m[x] = [x, 0]
    return m[x]
  if m[x][0] == x:
    return m[x]
  z = findi (m, m[x][0])
  m[x] = z
  return z

def find (m, x):
  return findi(m, x)[0]

def union (m, rep, x, y):
  xp = findi (m, x)
  yp = findi (m, y)
  if xp == yp:
    return
  if xp[1] < yp[1]:
    rep[yp[0]] = rep.get(xp[0], xp[0])
    if xp[0] in rep:
      del rep[xp[0]]
    m[xp[0]][0] = yp[0]
  elif xp[1] > yp[1]:
    m[yp[0]][0] = xp[0]
  else:
    m[yp[0]][0] = xp[0]
    m[xp[0]][1] += 1


def print_grouper_results (counts, rootLabels, docParents, docURLs, garb):
  garbage_total = 0
  in_doc_total = 0
  orphan_total = 0

  fout = open('counts.log', 'w')
  for x, n in counts.iteritems():
    fout.write('%(num)8d %(label)s' % {'num':n, 'label':x})
    if x in garb:
      garbage_total += n
      fout.write(' is garbage')
    if x in docParents:
      in_doc_total += n
      fout.write(' in document %(addr)s %(label)s\n' \
                   % {'addr':docParents[x], 'label':docURLs[docParents[x]]})
    else:
      orphan_total += n
      fout.write(' orphan from ' + rootLabels[x] + '\n')

  sys.stderr.write('Found %(num)d nodes in orphan DOMs.\n' % {'num':orphan_total})
  sys.stderr.write('Found %(num)d nodes in DOMs in documents.\n' % {'num':in_doc_total})
  sys.stderr.write('Found %(num)d garbage nodes in DOMs.\n' % {'num':garbage_total})
  fout.close()


def getURL(s):
  urlIndex = s.find("http://")
  if urlIndex != -1:
    return s[urlIndex:]
  urlIndex = s.find("https://")
  if urlIndex != -1:
    return s[urlIndex:]
  urlIndex = s.find("chrome://")
  if urlIndex != -1:
    return s[urlIndex:]
  urlIndex = s.find("about:")
  if urlIndex != -1:
    return s[urlIndex:]
  return s


nodePatt = re.compile ('([a-zA-Z0-9]+) \[(?:rc=[0-9]+|gc(?:.marked)?)\] (.*)$')
edgePatt = re.compile ('> ([a-zA-Z0-9]+) (.*)$')

def parseGraph (f):
  currNode = None
  currNodeLabel = ''

  nodeLabels = {}
  docsChildren = {}
  docURLs = {}
  doneCurrEdges = False
  isDoc = False

  m = {}
  rep = {}

  for l in f:
    if l[0] == '>':
      if doneCurrEdges:
        continue
      e = edgePatt.match(l)
      target = e.group(1)
      edgeLabel = e.group(2)
      if edgeLabel == 'GetParent()':
        assert(not isDoc)
        assert(currNode != None)
        doneCurrEdges = True
        union (m, rep, target, currNode)
      elif isDoc and edgeLabel == 'mChildren[i]':
        docsChildren[currNode].add(target)
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = nm.group(1)
        currNodeLabel = nm.group(2)
        isDoc = currNodeLabel.startswith('nsDocument')
        if isDoc:
          docsChildren[currNode] = set([])
          docURLs[currNode] = getURL(currNodeLabel)
        else:
          nodeLabels[currNode] = currNodeLabel
        doneCurrEdges = False
      elif l == '==========\n':
        break
      else:
        print 'Error: Unknown line:', l[:-1]

  (known, garb) = parse_cc_graph.parseResults(f)

  # invert the children map
  docParents = {}

  for x, s in docsChildren.iteritems():
    for y in s:
      assert(not y in docParents)
      docParents[y] = x


  # compute DOM trees.
  counts = {}
  trees = {}
  rootLabels = {}

  for x in m:
    y = find(m, x)
    if y in rep:
      y = rep[y]
    counts[y] = counts.get(y, 0) + 1
    if not y in trees:
      trees[y] = []
    trees[y].append(x)
    if y not in rootLabels:
      currLabel = nodeLabels[y]
      if currLabel.startswith("nsGenericElement (xhtml)"):
        currLabel = getURL(currLabel)
      elif currLabel.startswith("nsGenericElement (XUL)"):
        currLabel = getURL(currLabel)
      rootLabels[y] = currLabel

  # print out results
  print_grouper_results(counts, rootLabels, docParents, docURLs, garb)

  # print out merging information
  if True:
    for x, l in trees.iteritems():
      print x,
      for y in l:
        print y,
      print

  return trees


def mergeDOMParents (f, trees):
  sys.stderr.write('Merging DOM parents.\n')

  # compute direct DOM merge map
  merge = {}
  for x, l in trees.iteritems():
    for y in l:
      merge[y] = x

  currNode = None

  parentsOfDOM = {} # map from a DOM to types of DOM parents to a list of parent nodes pointing at that DOM
  inParent = False
  parentClass = None
  childField = None

  possibleChildren = set([])
  childrenOfDOM = {}

  # compute DOM parents to merge
  for l in f:
    if l[0] == '>':
      e = edgePatt.match(l)
      assert(e != None)
      target = e.group(1)
      edgeLabel = e.group(2)
      if inParent:
        assert(currNode != None)
        assert(childField != None)
        if edgeLabel != childField:
          continue
        domChild = merge.get(target, target)
        if not domChild in parentsOfDOM:
          parentsOfDOM[domChild] = {}
        if not parentClass in parentsOfDOM[domChild]:
          parentsOfDOM[domChild][parentClass] = []
        parentsOfDOM[domChild][parentClass].append(currNode)
        inParent = False
      elif edgeLabel == '[via hash] mListenerManager':
        assert(currNode != None)
        domParent = merge.get(currNode, currNode)
        # will have to do something else if we generalize this
        if not domParent in childrenOfDOM:
          childrenOfDOM[domParent] = []
        childrenOfDOM[domParent].append(target)
    else:
      nm = nodePatt.match(l)
      if nm:
        currNode = nm.group(1)
        currNodeLabel = nm.group(2)
        if currNodeLabel == 'nsDOMCSSAttributeDeclaration':
          inParent = True
          parentClass = 'nsDOMCSSAttributeDeclaration'
          childField = 'mElement'
          continue
        if currNodeLabel.startswith('XPCWrappedNative'):
          inParent = True
          parentClass = 'XPCWrappedNative'
          childField = 'mIdentity'
          continue
        inParent = False
        if currNodeLabel == 'nsEventListenerManager':
          possibleChildren.add(currNode)

      elif l.startswith('=========='):
        break
      else:
        print 'Error: Unknown line:', l[:-1]

  # print out parent merging information
  for m in parentsOfDOM.values():
    for l in m.values():
      print l[0],
      for y in l:
        print y,
      print

  # print out child
  elmCounts = 0
  for x, l in childrenOfDOM.iteritems():
    foundAny = False
    assert(len(l) != 0)
    if len(l) == 1:
      continue
    for y in l:
      if y in possibleChildren:
        foundAny = True
        elmCounts += 1
        print y,
        #sys.stderr.write(y + ' ')
    if foundAny:
      print
      #sys.stderr.write('\n')


def parseFile (fname):
  try:
    f = open(fname, 'r')
  except:
    print 'Error opening file', fname
    exit(-1)

  trees = parseGraph(f)
  f.close()

  f = open(fname, 'r')
  mergeDOMParents(f, trees)
  f.close()


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()

parseFile(sys.argv[1])
