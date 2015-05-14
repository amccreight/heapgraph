#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Find paths to a given object using a shortest-path algorithm.

import sys
import parse_gc_graph
from collections import deque


def findRoots(args, g, ga, target):
  print 'Finding roots.',

  workList = deque()
  distances = {}
  limit = 0

  rootNode = (0, 'ROOT')
  for r in ga.roots:
    distances[r] = rootNode
    workList.append(r)

  while workList:
    x = workList.popleft()
    dist = distances[x][0]

    # Check the monotonicity of workList.
    assert dist >= limit
    limit = dist

    if x == target:
      # Found target: nothing to do?
      # This will just find the shortest path to the object.
      continue

    if not x in g:
      # x does not point to any other nodes.
      continue

    newDist = dist + 1
    newDistNode = (dist + 1, x)

    for y in g[x]:
      if y in distances:
        assert distances[y][0] <= newDist
      else:
        distances[y] = newDistNode
        workList.append(y)

  print 'Done finding roots.',
  print

  path = []
  p = target
  while p in distances:
    path.append(p)
    [_, p] = distances[p]

  path.reverse()

  print path

  return


def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga) = parse_gc_graph.parseGCEdgeFile(fname)
  g = parse_gc_graph.toSinglegraph(g)
  print 'Done loading graph.',

  return (g, ga)


def findGCRoots():
  args = {}
  file_name = "gc-edges.71083.1431633807.log"

  (g, ga) = loadGraph(file_name)

  targ = "0x126431ec0"

  if targ in g:
    findRoots(args, g, ga, targ)
  else:
    sys.stdout.write('{0} is not in the graph.\n'.format(targ))


if __name__ == "__main__":
  findGCRoots()
