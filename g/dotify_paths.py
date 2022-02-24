#!/usr/bin/python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Experimental find_roots.py dotify support.


#######
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


#######
# dotify support

gPaths = []


def add_dot_mode_path(ga, path):
  gPaths.append(path)


def outputDotFile(args, ga, targs):

  # build the set of nodes
  nodes = set([])
  for p in gPaths:
    for x in p:
      nodes.add(x)

  # build the edge map
  edges = {}

  for p in gPaths:
    prevNode = None
    for x in p:
      if prevNode:
        edges.setdefault(prevNode, set([])).add(x)
      prevNode = x

  # compress shapes
  shape_merge = {}
  shape_rep = {}

  for x in nodes:
    if ga.nodeLabels.get(x, '') != 'shape':
      continue
    if not x in edges:
      continue
    for y in edges[x]:
      if ga.nodeLabels.get(y, '') != 'shape' and ga.nodeLabels.get(y, '') != 'base_shape':
        continue
      union(shape_merge, shape_rep, y, x)
      break

  def canon_node(x):
    y = find(shape_merge, x)
    if y in shape_rep:
      y = shape_rep[y]
    return y

  # Remove merged away nodes
  for x in list(shape_merge.keys()):
    if canon_node(x) != x:
      nodes.remove(x)

  # Update the edges for merging
  new_edges = {}
  for x, dsts in edges.items():
    new_dsts = set([])
    for y in dsts:
      new_dsts.add(canon_node(y))
    x = canon_node(x)
    if x in new_dsts:
      new_dsts.remove(x)
    new_edges[x] = new_edges.get(x, set([])).union(new_dsts)
  edges = new_edges


  # output the dot file

  outf = open('graph.dot', 'w')
  outf.write('digraph {\n')

  if len(targs) != 1:
    print('Had more than one target, arbitrarily picking the first one', targs[0])

  for n in nodes:
    lbl = ga.nodeLabels.get(n, '')
    if lbl.startswith('Object'):
      lbl = lbl[6:]
      shape = 'square'
      color = 'black'
    elif lbl.startswith('Function'):
      if len(lbl) > 10:
        lbl = lbl[9:]
      shape = 'ellipse'
      color = 'black'
    elif lbl.startswith('HTML'):
      lbl = lbl[4:]
      shape = 'diamond'
      color = 'blue'
    elif lbl.startswith('XPCWrappedNative'):
      lbl = 'XPCWN' + lbl[16:]
      shape = 'diamond'
      color = 'black'
    elif lbl.startswith('script'):
      if lbl.startswith('script app://system.gaiamobile.org/'):
        lbl = lbl[35:]
      else:
        lbl = lbl[7:]
      shape = 'ellipse'
      color = 'red'
    else:
      if lbl.startswith('WeakMap'):
        lbl = 'WeakMap'
      elif lbl == 'base_shape':
        lbl = 'shape'
      elif lbl == 'type_object':
        lbl = 'type'
      elif lbl.startswith('DOMRequest '):
        lbl = 'DOMRequest'
      shape = 'circle'
      color = 'black'
    if lbl.endswith('<no private>'):
      lbl = lbl[:-13]

    # this will def. not work with multiple targets
    if n == targs[0]:
      shape = 'tripleoctagon'
      lbl = 'TARGET'
      color = 'orange'

    if shape == 'ellipse':
      lbl = lbl[:30]
    else:
      lbl = lbl[:15]

    outf.write('  node [color = {3}, shape = {2}, label="{1}"] q{0};\n'.format(n, lbl, shape, color))

  for x, dsts in edges.items():
    for y in dsts:
      if args.dot_mode_edges:
        lbls = ga.edgeLabels.get(x, {}).get(y, [])
        ll = []
        for l in lbls:
          if len(l) == 2:
            l = l[0]
          if l.startswith('**UNKNOWN SLOT '):
            continue
          ll.append(l)
        outf.write('  q{0} -> q{1} [label="{2}"];\n'.format(x, y, ', '.join(ll)))
      else:
        outf.write('  q{0} -> q{1};\n'.format(x, y))

  outf.write('}\n')
  outf.close()
