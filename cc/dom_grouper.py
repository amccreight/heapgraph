#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# associate each DOM node with its uppermost parent.


import sys
import re
import parse_cc_graph
import argparse


# Argument parsing.

argparser = argparse.ArgumentParser(description='Group together DOM nodes into their topmost parent node by following parent chains.')
argparser.add_argument('file_name',
                       help='Cycle collector edge file name.')
argparser.add_argument('--only-orphans', '-oo', dest='only_orphans', action='store_true',
                       default=False,
                       help='Only print out information about orphan nodes')
argparser.add_argument('--no-garbage', '-ng', dest='no_garbage', action='store_true',
                       default=False,
                       help='Don\'t print out information about garbage')


args = argparser.parse_args()


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
  sys.stderr.write('Printing grouping results to counts.log\n')
  for x, n in counts.iteritems():
    print_this = True
    if args.only_orphans and x in docParents:
      print_this = False
    if args.no_garbage and x in garb:
      print_this = False

    if print_this:
      fout.write('%(num)8d %(label)s' % {'num':n, 'label':x})
    if x in garb:
      garbage_total += n
      if print_this:
        fout.write(' is garbage')
    if x in docParents:
      in_doc_total += n
      if print_this:
        fout.write(' in document %(addr)s %(label)s\n' \
                   % {'addr':docParents[x], 'label':docURLs[docParents[x]]})
    else:
      orphan_total += n
      if print_this:
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
weakMapEntryPatt = re.compile ('WeakMapEntry map=([a-zA-Z0-9]+|\(nil\)) key=([a-zA-Z0-9]+|\(nil\)) keyDelegate=([a-zA-Z0-9]+|\(nil\)) value=([a-zA-Z0-9]+)\r?$')

printMergingInformation = False


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
      elif l.startswith('#'):
        # skip comments
        continue
      else:
        wmem = weakMapEntryPatt.match(l)
        if wmem:
          # ignore weak map entries
          continue
        else:
          sys.stderr.write('Error: skipping unknown line:' + l[:-1] + '\n')

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
  if printMergingInformation:
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
      elif l.startswith('#'):
        # skip comments
        continue
      else:
        wmem = weakMapEntryPatt.match(l)
        if wmem:
          # ignore weak map entries
          continue
        else:
          sys.stderr.write('Error: Unknown line in mergeDOMParents: ' + l[:-1] + '\n')

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
    if foundAny:
      print


def parseFile (fname):
  try:
    f = open(fname, 'r')
  except:
    sys.stderr.write('Error opening file' + fname + '\n')
    exit(-1)

  trees = parseGraph(f)
  f.close()

  if printMergingInformation:
    f = open(fname, 'r')
    mergeDOMParents(f, trees)
    f.close()


parseFile(sys.argv[1])
