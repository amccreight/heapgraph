#!/usr/bin/python

import sys
import re
from collections import namedtuple
import parse_cc_graph
from optparse import OptionParser



# Parse graph data into a data structure, process it, produce a .dot file.

# This script takes a single argument, which is a digit indicating 
# which cc-edge file should be processed.  It should be invoked from
# the directory that contains the cc-edges file and pointer_log.

# The dot file can be converted into a .pdf file with
#    sfdp -Tpdf -O cc-edges-2.dot
# That will produce a pdf file cc-edges-2.dot.pdf
# If you trim down to a couple of subgraphs, you can sometimes use twopi or 
# dot instead of sfdp.

# These options improve the graph:
#     sfdp -Gsize=67! -Goverlap=prism -Tpdf -O

# Circles are refcounted DOM nodes, squares are GCed JS nodes,
# triangles are objects the CC has identified as garbage.




### Display options


usage = "usage: %prog [options] file_name\n\
  file_name is the name of the cycle collector graph file"
parser = OptionParser(usage=usage)

parser.add_option('--min',
                  action='store', dest='min_graph_size', type='int',
                  default=0,
                  help='minimum size of subgraph to display')

parser.add_option('--max',
                  action='store', dest='max_graph_size', type='int',
                  default=-1,
                  help='maximum size of subgraph to display')

parser.add_option('--show-labels',
                  action='store_true', dest='node_class_labels',
                  help='show labels of nodes')

parser.add_option('--show-edge-labels',
                  action='store_true', dest='edge_labels',
                  help='show labels of nodes')

parser.add_option('--show-addresses',
                  action='store_true', dest='node_address_labels',
                  help='show addresses of nodes')

parser.add_option('--html-labels',
                  action='store_true', dest='html_labels',
                  help='show tag labels for nsGenericElement (xhtml) nodes')

parser.add_option('--prune-js',
                  action='store_true', dest='prune_js',
                  help='prune JS nodes from the graph')

parser.add_option('--prune-non-js',
                  action='store_true', dest='prune_non_js',
                  help='prune non-JS nodes from the graph')

parser.add_option('--prune-marked-js',
                  action='store_true', dest='prune_marked_js',
                  help='prune marked JS nodes from the graph')

parser.add_option('--prune-garbage',
                  action='store_true', dest='prune_garbage',
                  help='prune garbage nodes from the graph')

parser.add_option('--min-copies',
                  action='store', dest='min_copies', type='int',
                  default=0,
                  help='only display subgraphs with at least this many copies')

options, args = parser.parse_args()


if len(sys.argv) < 2:
  print 'Not enough arguments.'
  exit()




# I really need to make a lot of these command line options.

precise_node_name = False    # use a more complete class name
       # eg "nsNodeInfo (xhtml) span" instead of "nsNodeInfo"

show_roots = True   # shade graph roots


SHOW_REF_COUNTS = False
  # show the internal counts and reference counts computed by the CC

onlyPrintGarbage = False
  # only print out graphs containing garbage.

# For graphs with 1, 2 and 3 nodes, we combine some or all that are
# displayed identically.  Set these to True to show them all.
# Probably mostly useful as a debugging option at this point.
print_all_singletons = False
print_all_pairs = False
print_all_tris = False


### Pruning options

COMPUTE_ACYCLIC = False   # compute set of nodes that are not members of cycles
REMOVE_ACYCLIC = False    # remove acyclic nodes.  if False, then just highlight them on the graph.
#ACYCLIC_DEPTH = 3         # one of the acyclic algorithms only works to a fixed depth

# This gets rid of a lot of boring parts of the graph, so it can be handy for browsing.
CALC_DUPS = True       # find JS nodes that duplicate other nodes (eg have same parents and children)
REMOVE_DUPS = False     # remove duplicates.  If False, highlight them on the graph.


####################







DrawAttribs = namedtuple('DrawAttribs', 'edgeLabels nodeLabels rcNodes gcNodes roots garbage colors')


####
#### Graph analysis
####


# compute set of source and target nodes
def graph_nodes (g):
  nodes = set([])
  for src, edges in g.iteritems():
    nodes |= set([src])
    nodes |= edges
  return nodes


# Basic graph analysis: how many edges, and the set of source and
# destination nodes.  For small graphs, this is enough information to
# classify the shape.
def graph_counts (g):
  num_edges = 0
  srcs = set([])
  dsts = set([])
  for src, edges in g.iteritems():
    num_edges += len(edges)
    if len(edges) != 0:
      srcs |= set([src])
    dsts |= edges
  return (num_edges, srcs, dsts)


# counting the acyclicity ranks of nodes  (see bug 641243)

def get_rank_0 (g):
  c = graph_counts(g)
  return graph_nodes(g) - c[1]

def get_rank_k (g, kprev):
  s = set([])
  for src, edges in g.iteritems():
    all_prev = True
    for e in edges:
      if not e in kprev:
        all_prev = False
        break
    if all_prev:
      s |= set([src])
  return s


# compute and print out acyclic nodes
def compute_acyclic (g, k, ga):
  num_nodes = len(graph_nodes(g))
  sys.stdout.write('total number of nodes is {0}.\n'.format(num_nodes))

  rnks = get_rank_0(g)

  prev_len = 0
  for x in range(k):
    l = len(rnks)
    #sys.stdout.write('{0},{1}\n'.format(x, l))
    sys.stdout.write('|acyc_{0}| = {1} / {2}  /  {3}%\n'.format(x, l, l - prev_len, (100 * l)/num_nodes))
    prev_len = l
    rnks = get_rank_k(g, rnks)

  return rnks


  # analyze zero-successor nodes
  #zero_counts = {}
  #s = set(['nsDocument', 'nsGenericDOMDataNode', 'nsGenericElement', 'nsDOMAttribute'])
  #for z in rnks:
  #  if z in ga.node_names and (not z in ga.roots or z in ga.black_rced):
  #    v = zero_counts.pop(ga.node_names[z], 0) + 1
  #    zero_counts[ga.node_names[z]] = v
  #total1 = 0
  #total2 = 0
  #for n, c in zero_counts.iteritems():
  #  print c, n
  #  if n in s:
  #    total1 += c
  #  else:
  #    total2 += c

  print 'zero covered:', total1, (100 * total1 / (total1 + total2)), '%'


# compute and print out acyclic nodes, but separate ranks
def compute_acyclic_sep (g, k):
  lrnks = {}
  rnks = get_rank_0(g)
  curr_rank = 0
  for x in rnks:
    lrnks[x] = curr_rank

  for x in range(k):
    rnks = get_rank_k(g, rnks)
    curr_rank += 1
    for x in rnks:
      if not x in lrnks:
        lrnks[x] = curr_rank

  return lrnks


def remove_nodes (g, s):
  ng = {}
  for src, edges in g.iteritems():
    if not src in s:
      ng[src] = edges - s
  return ng


# return an arbitrary set element
def set_select (s):
  for x in s:
    return x


# calculate all nodes with 1 ref that point to the node that points to them
# I'm not sure if this is useful.
def calc_tiny_loops (g, s):
  counts = computeRefCounts(g)
  tiny_mems = set([])
  for n, k in counts.items():
    if (not n in s) and k == 1 and n in g and len(g[n]) == 1:
      dst = set_select(g[n])
      if dst in g and n in g[dst]:
        tiny_mems |= set([n])

  return tiny_mems


# Generate inverse of graph: if a points to b in the graph, then in the inverse b points to a.
def graph_inverse (g):
  ng = {}
  for x, edges in g.iteritems():
    for e in edges:
      s = ng.pop(e, set([]))
      s |= set([x])
      ng[e] = s
  return ng


# If a and b have the same parents and successors, and they are both
# GCed we can remove one of them from the graph
def calc_dups (g, ga):
  gn = graph_nodes(g)
  gnodes = gn & ga.black_gced
  ginv = graph_inverse(g)
  eq_nodes = {}
  for x in gnodes:
    if x in ginv:
      ki = ginv[x]
    else:
      ki = set([])

    k = (frozenset(g[x]), frozenset(ki))
    s = eq_nodes.pop(k, set([]))
    eq_nodes[k] = s | set([x])

  dups = set([])
  for s in eq_nodes.values():
    dups |= s - set([set_select(s)])

  print len(dups), '/', len(gn), 'duplicate nodes (', (100 * len(dups) / len(gn)), '%)'

  return dups



# Calculate acyclic nodes in a lower level way.


def calc_acyc_dfs_rec (g, n, nodes, ng, has_children):
  if n in has_children:
    return has_children[n]
  if n in nodes:
    return True
  nodes.append(n)
  n_has_children = False
  
  if n in g:
    for e in g[n]:
      eacyc = calc_acyc_dfs_rec (g, e, nodes, ng, has_children)
      n_has_children |= eacyc
      if not eacyc:
        s = ng.pop(n, set([]))
        ng[n] = s | set([e])

  has_children[n] = n_has_children
  nodes.pop()
  return n_has_children
  

def calc_acyc_dfs (g):
  nodes = []
  ng = {}
  has_children = {}
  for x in g.keys():
    calc_acyc_dfs_rec (g, x, nodes, ng, has_children)

  pruned = set([])
  for x, hc in has_children.iteritems():
    if not hc:
      pruned |= set([x])

  print 'Found', len(pruned), ' acyclic nodes.'
  return pruned


# acyc with edge pooling

def calc_acyc_dfs_rec2 (g, n, edges, ng, has_children):
  if n in has_children:
    return 0
  has_children[n] = True   # temp value to prevent loops
  num_children = 0

  if n in g:
    for e in g[n]:
      num_gchildren = calc_acyc_dfs_rec2 (g, e, edges, ng, has_children)
      child_interesting = has_children[e]
      if child_interesting:
        num_children += 1
        edges.append(e)

  n_edges = set([]) 
  for i in range(num_children):
    n_edges |= set([edges.pop()])
  if num_children != 0:
    ng[n] = n_edges

  has_children[n] = num_children != 0
  return num_children
  

def calc_acyc_dfs2 (g):
  depth = 0
  edges = []
  ng = {}
  has_children = {}
  for x in g.keys():
    calc_acyc_dfs_rec2 (g, x, edges, ng, has_children)
  assert (edges == [])
  pruned = set([])
  for x, hc in has_children.iteritems():
    if not hc:
      pruned |= set([x])

  print 'Found', len(pruned), 'acyclic nodes.'
  return pruned



def commit_edges (g, edges, n, num_children):
  if num_children == 0:
    return
  n_edges = set([]) 
  for i in range(num_children):
    n_edges |= set([edges.pop()])
  g[n] = n_edges



# Compute acyclic and chained nodes.

def calc_acyc_dfs_rec3 (g, ch, n, edges, ng, has_children):
  if n in has_children:
    return 0
  has_children[n] = True   # temp value to prevent loops
  num_children = 0
  
  if n in g:
    for e in g[n]:
      num_inherit = calc_acyc_dfs_rec3 (g, ch, e, edges, ng, has_children)
      if has_children[e]:
        assert(num_inherit == 0)
        num_children += 1
        edges.append(e)
      else:
        num_children += num_inherit

  if n in ch:
    has_children[n] = False
    return num_children
  else:
    commit_edges(ng, edges, n, num_children)
    has_children[n] = num_children != 0
    return 0


def one_parent_rc_nodes (g, ga):
  rc = computeRefCounts(g)  
  # this computes the ref count from the graph, but we also don't
  # includes roots (which the CC has decided has external refs, so it
  # is a bit circular in terms of reasoning, but should simulate
  # external refs.

  s = set([])
  for x in g.keys():
    if x in rc and rc[x] == 1 and not x in ga.black_gced and not x in ga.roots:
      s |= set([x])
  return s

def calc_acyc_dfs3 (g, ga):
  edges = []
  ng = {}
  has_children = {}
  ch = one_parent_rc_nodes(g, ga)

  for x in g.keys():
    calc_acyc_dfs_rec3 (g, ch, x, edges, ng, has_children)
    # commit any remaining edges
    if len(edges) != 0:
      has_children[x] = True
      commit_edges(ng, edges, x, len(edges))

  pruned = set([])
  for x, hc in has_children.iteritems():
    if not hc:
      pruned |= set([x])

  print 'Found', len(pruned), 'acyclic and chained nodes.'
  return pruned


def paths_to (g, leak):
  work_list = set([leak])
  wlen = 1
  parents = set([leak])
  ginv = graph_inverse(g)

  while (wlen != 0):
    x = set_select(work_list)
    work_list.remove(x)
    wlen -= 1
    if x in ginv:
      for p in ginv[x]:
        if p in parents:
          continue
        work_list.add(p)
        parents.add(p)
        wlen += 1

  return remove_nodes(g, graph_nodes(g) - parents)
  



# union-find with path compression

def findOld (m, x):
  if not x in m:
    m[x] = x
    return x
  if m[x] == x:
    return x
  z = findOld (m, m[x])
  m[x] = z
  return z

def unionOld (m, x, y):
  xp = findOld (m, x)
  yp = findOld (m, y)
  m[xp] = yp


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

def union (m, x, y):
  xp = findi (m, x)
  yp = findi (m, y)
  if xp == yp:
    return
  if xp[1] < yp[1]:
    m[xp[0]][0] = yp[0]
  elif xp[1] > yp[1]:
    m[yp[0]][0] = xp[0]
  else:
    m[yp[0]][0] = xp[0]
    m[xp[0]][1] += 1


def ok_js_merge (ga, x):
  return x in ga.black_gced and not x in ga.roots

# if two non-root JS nodes point to each other, we can merge them safely.
# this will clear out a huge amount of JS tree mess, thanks to the parent pointer.
# once the parent pointer is gone, maybe acyclic stuff can clear some of it out.
def calc_js_mini_loop (g, ga):
  m = {}

  for n, edges in g.iteritems():
    for e in edges:
      if e in g and n in g[e] and ok_js_merge(ga, n) and ok_js_merge(ga, e):
        union(m, n, e)

  return m


# http://en.wikipedia.org/wiki/Cheriyan%E2%80%93Mehlhorn/Gabow_algorithm
# ignore concerns about GC v RC, marked, etc in this basic version
def calc_scc1 (g):
  pre = {}
  opens = []
  roots = []
  sccs = {}

  def dfs (v, C):
    pre[v] = C
    C += 1
    roots.append(v)
    opens.append(v)
    for w in g[v]:
      if not w in pre:
        C = dfs(w, C)
      elif not w in sccs:
        while pre[w] < pre[roots[-1]]:
          roots.pop()
    if v == roots[-1]:
      roots.pop()
      while 1:
        w = opens.pop()
        assert (not w in sccs)
        sccs[w] = v
        if w == v:
          break
    return C

  C = 0
  for v in g.keys():
    if not v in pre:
      C = dfs(v, C)

  return sccs


def check_scc_map (g, ga, m):
  print 'Checking scc results:',
  sccs = calc_scc1(g)
  fwdMap = {}

  for x, v1 in sccs.iteritems():
    if v1 in fwdMap:
      if fwdMap[v1] != m[x]:
        print 'WRONG!'
        exit(-1)
    else:
      fwdMap[v1] = m[x]

  assert(len(fwdMap.keys()) == len(fwdMap.values()))

  print 'ok.'

  # take a census of the non-trivial SCCs
  s = {}
  for x, v in m.iteritems():
    z = s.pop(v, set([]))
    assert(not x in z)
    z.add(x)
    s[v] = z

  puregs = 0
  purers = 0
  garbs = 0
  mixed = 0

  gclen = 0
  rclen = 0
  mixedlen = 0
  garblen = 0

  mixedSCC = []

  for gr in s.values():
    if len(gr) == 1:
      continue
    pureGC = True
    pureRC = True
    garb = False
    for x in gr:
      if x in ga.black_rced:
        pureGC = False
      elif x in ga.black_gced:
        pureRC = False
      else:
        garb = True
    if garb:
      garbs += 1
      garblen += len(gr)
    elif pureGC:
      puregs += 1
      gclen += len(gr)
    elif pureRC:
      purers += 1
      rclen += len(gr)
    else:
      mixed += 1
      mixedlen += len(gr)
      mixedSCC.append(gr)
  sys.stdout.write ('pure RC={0}:{1}, pureGC={2}:{3}, mixed={4}:{5}, garb={6}:{7}\n'.format\
                      (purers, rclen, puregs, gclen, mixed, mixedlen, garbs, garblen))


  for scc in mixedSCC:
    if len(scc) < 10:
      continue
    sccsum = {'rc':0, 'gc':0}
    for x in scc:
      if x in ga.black_rced:
        sccsum['rc'] += 1
      elif x in ga.black_gced:
        sccsum['gc'] += 1
      else:
        print 'Did not expect garbage in a mixed SCC.'
        exit(-1)
    total = sccsum['gc'] + sccsum['rc']
    print (100 * sccsum['gc'] / total), '% out of', total, '((rc=', sccsum['rc']



# explicit recursion stack
def calc_scc2 (g, ga):
  pre = {}
  scc = set([])
  C = 0
  rootsStack = []
  openStack = []
  m = {}

  unvisitedGrandchildren = 0
  openGrandchildren = 0
  closedGrandchildren = 0

  def nonTreeEdge (v):
    if not v in scc:
      while pre[v] < pre[rootsStack[-1]]:
        rootsStack.pop()

  for v in g.keys():
    if not v in pre:
      controlStack = [v]

      while controlStack != []:
        v = controlStack[-1]
        if v == True:
          # finished the children for the top node
          controlStack.pop()
          v = controlStack.pop()
          # finishNode
          if rootsStack[-1] == v:
            rootsStack.pop()
            while 1:
              w = openStack.pop()
              assert (not w in scc)
              scc.add(w)
              assert (not w in m)
              m[w] = v
              if w == v:
                break

            # check status of grandchildren
            for w in g[v]:
              for e in g[w]:
                if not e in pre:
                  unvisitedGrandchildren += 1
                elif e in scc:
                  closedGrandchildren += 1
                else:
                  openGrandchildren += 1

          # /finishNode
        else:
          if v in pre:
            controlStack.pop()
            nonTreeEdge(v)
          else:
            # new node
            pre[v] = C
            C += 1
            # treeEdge
            openStack.append(v)
            rootsStack.append(v)
            controlStack.append(True)
            # /treeEdge
            for w in g[v]:
              if w in pre:
                nonTreeEdge(w)
              else:
                controlStack.append(w)

  print 'Grandchild analysis'
  print '  unvisited grandchildren:', unvisitedGrandchildren
  print '  open grandchildren', openGrandchildren
  print '  closed grandchildren', closedGrandchildren

  return m


# store DFS numbers in rootsStack instead of node names
def calc_scc3 (g, ga):
  pre = {}
  scc = set([])
  C = 0
  rootsStack = []
  openStack = []
  m = {}

  def nonTreeEdge(v):
    if not v in scc:
      while pre[v] < rootsStack[-1]:
        rootsStack.pop()

  for v in g.keys():
    if not v in pre:
      controlStack = [v]

      while controlStack != []:
        v = controlStack[-1]
        if v == True:
          # finished the children for the top node
          controlStack.pop()
          vdfs = controlStack.pop()
          v = controlStack.pop()
          # finishNode
          if rootsStack[-1] == vdfs:
            rootsStack.pop()
            while 1:
              w = openStack.pop()
              assert (not w in scc)
              scc.add(w)
              assert (not w in m)
              m[w] = v
              if w == v:
                break
          # /finishNode
        else:
          if v in pre:
            controlStack.pop()
            nonTreeEdge(v)
          else:
            # new node
            pre[v] = C
            # treeEdge
            openStack.append(v)
            rootsStack.append(C)
            controlStack.append(C)
            controlStack.append(True)
            # /treeEdge
            C += 1
            for w in g[v]:
              if w in pre:
                nonTreeEdge(w)
              else:
                controlStack.append(w)

  return m


# combine pre, scc and m into nodeState
#   nodeState represents the hash table mapping pointers
#   the boolean is the low bit of the value being mapped to
def calc_scc (g, ga):
  nodeState = {}
    # if not x in nodeState, x is unvisited
    # nodeState[x] = (True, n)   node open, preorder num of n
    # nodeState[x] = (False, y)  node closed, merge with y
  dfsNum = 0
  rootsStack = []
  openStack = []

  def nonTreeEdge(v):
    nsw = nodeState[v]
    if nsw[0]:
      while nsw[1] < rootsStack[-1]:
        rootsStack.pop()

  for v in g.keys():
    if not v in nodeState:
      controlStack = [v]

      while controlStack != []:
        v = controlStack[-1]
        if v == True:
          # finished the children for the top node
          controlStack.pop()
          vdfs = controlStack.pop()
          v = controlStack.pop()
          # finishNode
          if rootsStack[-1] == vdfs:
            rootsStack.pop()
            while 1:
              w = openStack.pop()
              assert (w in nodeState)
              assert (nodeState[w])
              nodeState[w] = (False, v)
              if w == v:
                break
          # /finishNode
        else:
          if v in nodeState:
            controlStack.pop()
            nonTreeEdge(v)
          else:
            # new node
            nodeState[v] = (True, dfsNum)
            # treeEdge
            openStack.append(v)
            rootsStack.append(dfsNum)
            controlStack.append(dfsNum)
            controlStack.append(True)
            # /treeEdge
            dfsNum += 1
            for w in g[v]:
              if w in nodeState:
                nonTreeEdge(w)
              else:
                controlStack.append(w)

  # convert nodeState to a merge map
  m = {}
  for n, ns in nodeState.iteritems():
    assert(not ns[0])
    m[n] = ns[1]

  return m




# Perform the graph transformation at the same time
#   nodeState represents the hash table mapping pointers
#   the boolean is the low bit of the value being mapped to
#
#  - Need to store the node data somewhere (edges, rc, etc.)  Do this
#    in openStack: when you push a node, push all of its data.  This
#    does mean we are storing edge data twice, once for control, and
#    once for data.
#
#  - Must eliminate self edges on merged objects.  This is a bigger
#    problem than the stats I generate suggest, as the Python graph
#    representation doesn't allow double edges.  May have to do two
#    passes over the stack.  first to set up nodeState, then the
#    second to allocate the edges, so we can make sure that all JS
#    nodes in the SCC get their final thing.
#
#  - Experimentally, it appears that when we finish off an SCC that
#    all grandchildren, aside from members of the SCC, are closed, so
#    we don't have to go patch and patch up edges.  Conceptually, this
#    kind of makes sense to me, but I should convince myself it is
#    true a bit more thoroughly.

# Should really make this an all-new graph with new names...


# This needs to be more sophisticated and deal with GCed vs RCed nodes.


# first pass (backwards?)
#   map every node in the SCC to the canonical node in the hash table
#   for every RC node in the SCC
#     allocate a new node with a ref count of 1, with no children
#     overwrite the node pointer in the stack with the new location
#
# allocate the canonical node
#
# second pass (forwards?)
#   for every non-self-edge encountered, add it to the canonical node
#   for every self-edge encountered, add to the self edge count
#   for every RC node encountered, add it as an edge in the canonical node
#      increment the RC
#   if a root GC node is encountered, record that
#
#  RC of canonical node = +inf                   if we encountered a GC root
#                       = total RC - self edges  otherwise
#  what about RC vs IC?  How should self edges not in the model graph be accounted for?
#
#  There is no IC for any of the nodes in the SCC yet, hopefully, as
#  this whole thing only works if we don't have to allocate the nodes
#  before this point.

#allocate an RC node and a JS node.  Make them point to each other.
#
#Scan over all nodes.  Map RC node to the RC node, and JS to the JS node.
#  while you are doing this, sum up the RC for the RC nodes, see if any JS nodes are roots.

#scan over all edges, forwarding them all.  If a node forwards to the
#JS or RC node, dont allocate it.  If it forwards to the RC node,
#increment an RC count.  The ref count of the RC node is the total RC
#count, minus the internal count.  The JS node is a root if any of the
#JS nodes are.

#the drawback of this is that we are always allocating a RC and GC
#node for every SCC.  It seems like this would have fairly small
#overhead, as there aren't that many pure SCCs.  The problem is that
#you don't know ahead of time if you are pure or not.  well, I guess
#you can allocate on demand, though that adds branches inside the
#loop.  But I guess it is already very branchy.  So maybe I'll try
#that.


# The structure of this suggests having separate edge and node stacks.
# though somehow the edge stack has to know when to stop, so it seems
# like it would end up being similar to the node stack anyways.
# Though you could count how many nodes are being marked, then
# separate the edges with a NULL pointer or whatever, and just pop off
# the edges for that many nodes.

# as you are scanning, see if there are any RC nodes and if there are any JS nodes.


def calc_scc_merge (g, ga):
  nodeState = {}
    # if not x in nodeState, x is unvisited
    # nodeState[x] = (True, n)   node open, preorder num of n
    # nodeState[x] = (False, y)  node closed, merge with y
  dfsNum = 0
  rootsStack = []
  openStack = []
  ng = {}

  def nonTreeEdge(v):
    nsw = nodeState[v]
    if nsw[0]:
      while nsw[1] < rootsStack[-1]:
        rootsStack.pop()

  # in real implementation, allocate a node
  def newName(v):
    return v + 'x'

  # scan over nodes, update nodeStates to forward appropriately
  def forwardNodes (v):
    newv = newName(v)
    i = -1
    while 1:
      # skip over the edges
      while openStack[i] != True:
        i -= 1
      i -= 1 # skip over the marker
      w = openStack[i]
      assert (w in nodeState)
      assert (nodeState[w][0])
      nodeState[w] = (False, newv)
      if w == v:
        return newv
      if not w in ga.black_gced:   # treat garbage nodes as RCed here...
        # create a stub node if w != v
        openStack[i] = newName(w)
        # set info for the new node (RC=1, etc.)

      # skip over any node data

  # We dont want to sum up ALL self-edges, only those that point to RC
  # nodes.

  # The simplest way to do this is to condense to two nodes, one for
  # RC and one for GC.

  # To avoid the problem with mixed loops, put all of the out edges on
  # one of them, then doubly-link the two nodes together.

  def commitEdges (newv):
    selfEdges = 0
    while 1:
      e = openStack.pop()
      if e == True:
        return selfEdges
      assert(not nodeState[e][0])
      newe = nodeState[e][1]
      if newe != newv:
        newEdges.add(newe)
      else:
        selfEdges += 1

  def commitNodes (v, newv):
    assert(not nodeState[v][0])
    newEdges = set([])
    foundRoot = False
    selfEdges = 0
    #newRC = 0
    while 1:
      selfEdges += commitEdges(newv)
      w = openStack.pop()
      # pop other node data

      if w in ga.black_gced:
        foundRoot = foundRoot or w in roots
      #else:
      #  newRC += rc(w)

      if w == v:
        break
      if not w in ga.black_gced:
        # add edge to stub node
        newEdges.add(w)
        
    assert(not newv in ng)
    ng[newv] = newEdges
    # if foundRoot:
    #   ng[newv].rc = +inf
    # else:
    #   ng[newv].rc = newRC - selfEdges

  for v in g.keys():
    if not v in nodeState:
      controlStack = [v]

      while controlStack != []:
        v = controlStack[-1]
        if v == True:
          # finished the children for the top node
          controlStack.pop()
          vdfs = controlStack.pop()
          v = controlStack.pop()
          # finishNode
          if rootsStack[-1] == vdfs:
            rootsStack.pop()
            newv = forwardNodes(v)
            commitNodes(v, newv)
          # /finishNode
        else:
          if v in nodeState:
            controlStack.pop()
            nonTreeEdge(v)
          else:
            # new node
            nodeState[v] = (True, dfsNum)
            # treeEdge
            # any other data needed to build the node gets shoved onto openStack here
            openStack.append(v)
            openStack.append(True)
            rootsStack.append(dfsNum)
            controlStack.append(dfsNum)
            controlStack.append(True)
            # /treeEdge
            dfsNum += 1
            for w in g[v]:
              openStack.append(w)
              if w in nodeState:
                nonTreeEdge(w)
              else:
                controlStack.append(w)

  return ng



###
### Split the large graph into disconnected components.
###

# Splitting the graph makes further analysis much easier.

# Implemented with a union-find algorithm.

def split_graph (g):
  m = {}

  for src, edges in g.iteritems():
    for dst in edges:
      union (m, src, dst)

  gg = {}
  for src, edges in g.iteritems():
    src2 = find(m, src)
    gg2 = gg.pop(src2, {})
    gg2[src] = g[src]
    gg[src2] = gg2
  
  return gg.values()


# node_format_string computes the string used to describe a node: By
# using this string as a key for the combining algorithms, we can
# combine or split precisely according to how the nodes are displayed,
# even as options change.

def node_label_string (x, ga):
  if options.html_labels:
    l = ga.nodeLabels[x]
    if l.startswith('nsGenericElement (xhtml)'):
      return '<' + l[25:] + '>'
    if l.startswith('nsGenericElement (XUL)'):
      return '<<' + l[23:] + '>>'
  if options.node_class_labels and x not in ga.colors:
    label = ga.nodeLabels[x]
    # should spin this out into a more comprehensive label canonization
    if label.startswith('nsDocument normal (xhtml)'):
      label = 'nsDocument normal (xhtml)';
  elif options.node_address_labels:
    label = x
  else:
    label = ''
  if SHOW_REF_COUNTS and x in ga.ref_counts:
    label += ' (' + str(ga.ref_counts[x][0]) + '/' + str(ga.ref_counts[x][1]) + ')'
  return label


def node_format_string (x, ga):
  s = ''

  # style
  #if x in ga.shadies or (x in ga.roots and show_roots):
  if x in ga.roots and show_roots:
    s += 'style=filled, '

  l = node_label_string(x, ga)
  s += 'label="' + l + '", '

  # color
  if x in ga.colors:
    s += 'color=' + ga.colors[x] + ', '

  # shape
  if x in ga.rcNodes:
    if x in ga.garbage:
      shape = 'triangle'
    elif l != '':
      shape = 'ellipse'
    else:
      shape = 'circle'
  else:
    assert(x in ga.gcNodes)
    if x in ga.garbage:
      shape = 'invtriangle'
    elif options.node_class_labels:
      shape = 'box'
    else:
      shape = 'square'
  s += 'shape=' + shape + ', '
  return s


# return the number of nodes in a graph
def gnodes (g):
  return len(graph_nodes(g))


# For all graphs of size 1 and 2, and some of size 3, we aggregate
# graphs that will be displayed identically (except I think for edge
# names, which we ignore).


# Analyze a graph of size 1.

def analyze_1_graph (x, solo_graphs, ga):
  z = x.keys()[0]
  p = (len(x[z]), node_format_string (z, ga))
  l = solo_graphs.pop(p, [])
  l.append(x)
  solo_graphs[p] = l


# turn a set of edges into a unique key
def set_to_type_list (s, ga):
  l = []
  for x in s:
    l.append(x)
  l = map(lambda x: node_format_string (x, ga), l)
  l.sort()
  return tuple(l)


# Analyze a graph with two nodes.
def analyze_2_graph(x, pair_graphs, ga):
  c = graph_counts(x)
  p = (c[0], set_to_type_list(c[1], ga), set_to_type_list(c[2], ga))
  l = pair_graphs.pop(p, [])
  l.append(x)
  pair_graphs[p] = l
  return True


# In a simple loop a -> b, b -> c, c -> a, choose the 
# the node with the least node_format_string as the first part of the key.
def pure_cycle_head (nn, ga):
  l = []
  for x in nn:
    l.append(x)
  l.sort(key = lambda x:node_format_string (x, ga))
  return l[0]

# Combine graphs with three nodes.  Unlike for 1 and 2, this is not
# complete: we just cover a few common cases.  We return True if we've
# classified the graph and added it to tri_graphs, otherwise return
# False so it can get added to the default case.
def analyze_3_graph (g, tri_graphs, ga):
  c = graph_counts(g)
  if c[0] == 2:
    # only 2 edges
    hd = set_to_type_list(c[1] - c[2], ga)  # source, but not dest, of edges
    mid = set_to_type_list(c[1] & c[2], ga) # source and dest of edges
    tl = set_to_type_list(c[2] - c[1], ga) # dest but not source of edges
    # create key
    gt = (2, hd, mid, tl)
    # push current graph onto combiner at key
    gsub = tri_graphs.pop(gt, [])
    gsub.append(g)
    tri_graphs[gt] = gsub
    return True
  elif c[0] == 3 and len(c[1]) == 3 and len(c[2]) == 3:
    # must be a pure cycle: select the node with the 'least' type
    # as the first part of the key, then the successor node,
    # then the last node.
    hd = pure_cycle_head(c[2], ga)
    mid = set_select(g[hd])
    tl = set_select(g[mid])
    gt = (3, node_format_string(hd, ga),
          node_format_string(mid, ga), node_format_string(tl, ga))
    gsub = tri_graphs.pop(gt, [])
    gsub.append(g)
    tri_graphs[gt] = gsub
    return True
  else:
    return False


# only pass in things with 11 nodes
def analyze_death_star (g, death_stars, ga):
  nodes = graph_nodes(g)
  center_node = None
  points = []

  for n in nodes:
    l = len(g[n])
    if l == 1:
      if center_node == None:
        center_node = set_select(g[n])
        points = [node_format_string(n, ga)]
      else:
        if set_select(g[n]) == center_node:
          points.append(node_format_string(n, ga))
        else:
          return False
    elif l == 10:
      if center_node == None:
        center_node = n
      elif center_node != n:
        return False
    else:
      return False

  if center_node == None:
    return False

  assert(len(points) == 10)

  points.sort()
  k = (node_format_string(center_node, ga), tuple(points))
  ds = death_stars.pop(k, [])
  ds.append(g)
  death_stars[k] = ds

  return True
      



# if this is true, at least one node in the graph is CC garbage
def has_garbage (x, ga):
  return len((graph_nodes(x) - ga.black_rced) - ga.black_gced) != 0

def should_print_graph (x, ga, num):
  if onlyPrintGarbage:
    return has_garbage(x, ga)
  else:
    return num > options.min_copies

  # another useful predicate would be a "has shady" predicate


def node_count_label_string (x, count, ga):
  s = node_label_string(x, ga)
  if s == '':
    return str(count)
  else:
    return s + ':' + str(count)

# functions to print out the result of analysis



# Print out a dot representation of a graph.
def print_graph (outf, g, ga):
  allNodes = graph_nodes(g)

  for src, edges in g.iteritems():
    for dst in edges:
      if options.edge_labels and src in ga.edgeLabels \
            and dst in ga.edgeLabels[src]:
        # could be more than one, in which case we just show the first for simplicity
        edge_name = 'label="{0}"'.format(ga.edgeLabels[src][dst][0])
      else:
        edge_name = ''

      if (src in ga.rcNodes and dst in ga.gcNodes) or (src in ga.gcNodes and dst in ga.rcNodes):
        outf.write('  q{0} -> q{1} [style=dashed, {2}];\n'.format(src, dst, edge_name))
      else:
        outf.write('  q{0} -> q{1} [{2}];\n'.format(src, dst, edge_name))

  for r in allNodes:
    outf.write('  q{0} [{1}];\n'.format(r, node_format_string(r, ga)))


# print out dot representations of the single node graphs
def print_solo_graphs(outf, solo_graphs, ga):
  for p, x in solo_graphs.iteritems():
    if print_all_singletons:
      for y in x:
        print_graph(outf, y, ga)
    else:
      if should_print_graph(x[0], ga, len(x)):
        print_graph(outf, x[0], ga)
        n = x[0].keys()[0]
        outf.write('  q{0} [label="{1}"];\n'.format(n, node_count_label_string(n, len(x), ga)))


# print out dot representations of two node graphs
def print_pair_graphs (outf, pair_graphs, ga):
  for p, l in pair_graphs.iteritems():
    if should_print_graph(l[0], ga, len(l)):
      if print_all_pairs:
        for x in l:
          print_graph(outf, x, ga)
      else:
        print_graph(outf, l[0], ga)
        if len(l[0][l[0].keys()[0]]) != 0:
          hd = l[0].keys()[0]
        else:
          hd = l[0].keys()[1]
        le = len(l)
        if le != 1:
          outf.write('  q{0} [label="{1}"];\n'.format(hd, node_count_label_string(hd, le, ga)))

# print out dot representations of three node graphs
def print_tri_graphs (outf, tri_graphs, ga):
  for p, l in tri_graphs.iteritems():
    if should_print_graph(l[0], ga, len(l)):
      if print_all_tris:
        for x in l:
          print_graph(outf, x, ga)
      else:
        print_graph(outf, l[0], ga)
        if len(l) != 1:
          c = graph_counts(l[0])
          hd = set_select(c[1] - c[2])
          if hd == None:
            hd = set_select(c[1] & c[2])
          outf.write('  q{0} [label="{1}"];\n'.format(hd, node_count_label_string(hd, len(l), ga)))


# assume g is a death star
def death_star_head (g):
  for x, e in g.iteritems():
    if len(e) == 10:
      return x
  assert(False)


def print_death_stars (outf, death_stars, ga):
  for k, ds in death_stars.iteritems():
    if should_print_graph(ds[0], ga, len(ds)):
      print_graph(outf, ds[0], ga)
      # only add a count label if the count isn't 1
      if len(ds) != 1:
        hd = death_star_head(ds[0])
        outf.write('  q{0} [label="{1}"];\n'.format(hd, node_count_label_string(hd, len(ds), ga)))


##################
##################


if False:
  print 'didn\'t add', len(no_children_parse()), 'nodes with no children.'
  assert(no_children_parse() == get_rank_0(g))


def merge_map_lookup (m, x):
  if x in m:
    # only merge if both are GCed
    if x in ga.black_gced and m[x] in ga.black_gced:
      return m[x]
    else:
      return x
  else:
    return x


def calc_loopynodes (m):
  loopynodes = set([])
  for x in m.keys():
    if merge_map_lookup(m, x) != x:
      loopynodes.add(x)
  return loopynodes


if False:
  # m = calc_js_mini_loop (g, ga)
  m = calc_scc (g, ga)
  # g2 = calc_scc_merge (g, ga)

  assert (m == calc_scc2(g, ga))
  check_scc_map (g, ga, m)

  loopynodes = calc_loopynodes(m)
  gn = graph_nodes(g)
  gOrigLen = len(gn)
  print 'approx num JS nodes:', len(gn - ga.black_rced)
  sys.stdout.write('found {0} out of {1} ({2}%) useless nodes in loops'.format( \
    len(loopynodes), gOrigLen, 100 * len(loopynodes) / gOrigLen))

#  m2 = calc_scc2 (g, ga)
#  s = calc_loopynodes(m2) - loopynodes
#
#  for x in s:
#    print x, x in ga.black_gced, ':',
#    if m2[x] == x:
#      print 'ident', ';',
#    else:
#      print m2[x], m2[x] in ga.black_gced, ';',
#    if m[x] == x:
#      print 'ident'
#    else:
#      print m[x], m[x] in ga.black_gced


  if False:
    print '(marking)'
    ga = ga._replace(shadies = loopynodes)
  else:
    print '(merging)'
    ng = {}
    for x, edges in g.iteritems():
      x2 = merge_map_lookup(m, x)

      # if the node being merged away is a root, make the survivor a root
      if x in ga.roots and not x2 in ga.roots:
        ga = ga._replace(roots = ga.roots.add(x2))

      edges2 = ng.pop(x2, set([]))
      ne = set([])
      for e in edges:
        ne.add(merge_map_lookup(m, e))

      ng[x2] = ne | edges2

    g = ng

    gn = graph_nodes(g)
    assert(gOrigLen - len(loopynodes) == len(gn))

    print 'approx num JS nodes:', len(gn - ga.black_rced)


# remove JS self-loops
if False:
  ng = {}
  nsl = 0
  for x, edges in g.iteritems():
    if x in ga.black_gced:
      nedges = set([])
      for e in edges:
        if e != x:
          nedges.add(e)
        else:
          nsl += 1
    else:
      nedges = edges
    ng[x] = nedges

  print 'removed', nsl, 'self-loops from JS objects'

  g = ng


if COMPUTE_ACYCLIC:
  #acycnodes = compute_acyclic(g, ACYCLIC_DEPTH, ga)
  acycnodes = calc_acyc_dfs2(g)
  #acycnodes = calc_acyc_dfs3(g, ga)

  #acycnodes = get_rank_0(g)
  if REMOVE_ACYCLIC:
    print 'removing acyclic nodes'
    g = remove_nodes(g, acycnodes)
    # can't just remove the calculated nodes with dfs3
  else:
    print 'marking acyclic nodes'
    ga = ga._replace(shadies = ga.shadies | acycnodes)    

  if False:
    careAbout = set(['nsDocument', 'nsGenericDOMDataNode', 'nsGenericElement', 'nsDOMAttribute'])
    # show the classes of the acyclic nodes
    cyc_counts = {}
    for x in graph_nodes(g):
      (a, b) = cyc_counts.pop(ga.node_names[x], (0, 0))
      if x in acycnodes:
        cyc_counts[ga.node_names[x]] = (a+1, b)
      else:
        cyc_counts[ga.node_names[x]] = (a, b+1)
    for x, (v, w) in cyc_counts.iteritems():
      if not x in careAbout:
        continue
      if True: #v + w > 50:
        print '%(perc)3d%% %(cl)s (out of %(tot)d)' % \
            {"perc":(100 * v / (v + w)), "ac":v, "tot":v+w, "cl" : x}


# don't remove acyclic nodes after this, as we must keep around the graph residue
#tiny_mems = calc_tiny_loops (g, black_gced)
#print 'found', len(tiny_mems), 'tiny loops nodes to remove (', 100 * len(tiny_mems) / len(graph_nodes(g)) , '% )'
#g = remove_nodes(g, tiny_mems)



def node_info_string (x, ga):
  if x in ga.node_names:
    return '0' + x + ' [' + ga.node_names[x] + ']'
  else:
    return '0' + x
  
def edge_name_string (x, y, ga):
  if (x, y) in ga.edge_names:
    return 'via ' + ga.edge_names[(x,y)]
  else:
    return ''


# main


solo_graphs = {}
pair_graphs = {}
tri_graphs = {}
death_stars = {}
other_graphs = []
size_counts = {}



def generic_remover (g, pred, desc):
  nn = set([])
  count = 0
  
  for x in g.keys():
    if pred(x):
      nn.add(x)
      del g[x]
      count += 1

  print 'Removed', count, desc

  for x in g.keys():
    g[x] = g[x] - nn



def prune_no_childs (g):
  def no_ch_pred (x):
    return len(g[x]) == 0

  generic_remover (g, no_ch_pred, 'childless nodes.')


def prune_js (g, ga):
  gcn = set(ga.gcNodes.keys())

  def js_pred (x):
    return x in gcn

  generic_remover (g, js_pred, 'JS nodes.')


def prune_non_js (g, ga):
  gcn = set(ga.gcNodes.keys())

  def js_pred (x):
    return not x in gcn

  generic_remover (g, js_pred, 'non-JS nodes.')


def prune_marked_js (g, ga):
  s = set([])
  for x, marked in ga.gcNodes.iteritems():
    if marked:
      s.add(x)

  def js_pred (x):
    return x in s

  generic_remover (g, js_pred, 'marked JS nodes.')


def prune_js_listener (g, ga):
  def js_listener_pred (x):
    return ga.nodeLabels.get(x, '') == 'nsJSEventListener'

  generic_remover (g, js_listener_pred, 'JS listeners.')


def prune_garbage (g, ga):
  def garb_pred (x):
    return x in ga.garbage

  generic_remover (g, garb_pred, 'garbage nodes.')


# these create a lot of noise in the graph
def prune_info_parent_edges (g, ga):
  count = 0
  for x in g.keys():
    for e in list(g[x]):
      ename = ga.edgeLabels[x].get(e, [''])[0]
      if ename == 'mNodeInfo' or ename == 'GetParent()':
        g[x].remove(e)
        count += 1

  print 'Removed', count, 'nsNodeInfo and GetParent() edges.'

# analyze the graphs

def analyze_graphs():
  for x in gg:
    num_nodes = gnodes(x)

    scnn = size_counts.pop(num_nodes, 0)
    size_counts[num_nodes] = scnn + 1

    if num_nodes < options.min_graph_size or \
          not (num_nodes <= options.max_graph_size or options.max_graph_size == -1):
      continue
    if num_nodes == 1:
      analyze_1_graph (x, solo_graphs, ga)
    elif num_nodes == 2 and analyze_2_graph(x, pair_graphs, ga):
      continue
    elif num_nodes == 3 and analyze_3_graph(x, tri_graphs, ga):
      continue
    elif num_nodes == 11 and analyze_death_star(x, death_stars, ga):
      continue
    else:
      other_graphs.append((num_nodes, x))


label_color = {'nsJSEventListener':'purple',
               'nsXULPrototypeNode':'pink',
               'nsGenericDOMDataNode':'red'}

#               'nsGenericElement (xhtml) form':'green',
#               'nsGenericElement (xhtml) input':'yellow',
#               'nsGenericElement (xhtml) a':'red',
#               'nsGenericElement (xhtml) textarea':'orange',
#               'nsGenericElement (xhtml) html':'blue',
#               'nsGenericElement (xhtml) script':'blue',



def make_colors (nodeLabels):
  colors = {}
  for x, lbl in nodeLabels.iteritems():
    if lbl in label_color:
      colors[x] = label_color[lbl]
    elif lbl.startswith('nsGenericElement (XUL)'):
      colors[x] = 'green'
    elif lbl.startswith('nsGenericElement (xhtml)'):
      colors[x] = 'blue'
    elif lbl == 'nsBaseContentList':
      colors[x] = 'orange'
    elif lbl == 'nsContentSink':
      colors[x] = 'magenta'
  return colors


def make_draw_attribs (ga, res):
  roots = set([])

  for x, marked in ga.gcNodes.iteritems():
    if marked:
      roots.add(x)

  for x in res[0]:
    roots.add(x)

  return DrawAttribs (edgeLabels=ga.edgeLabels, nodeLabels=ga.nodeLabels,
                      rcNodes=ga.rcNodes, gcNodes=ga.gcNodes, roots=roots,
                      garbage=res[1], colors=make_colors(ga.nodeLabels))


# remove graph nodes that aren't within k steps of nodes of a given name
def split_neighbor (g, ga, name, k):
  visited = {}

  def flood (n, l):
    if l > k or (n in visited and visited[n] <= l):
      return
    visited[n] = l
    if len(g[n]) > 10:
      return
    for e in g[n]:
      flood(e, l+1)

  # get objects that are close
  for n in g:
    if ga.nodeLabels.get(n, '') == name:
      flood(n, 1)

  visited = set(visited.keys())

  # remove other objects
  for n in g.keys():
    if n in visited:
      g[n] = g[n] & visited
    else:
      del g[n]


def loadGraph(fname):
  sys.stdout.write ('Parsing {0}. '.format(fname))
  sys.stdout.flush()
  (g, ga, res) = parse_cc_graph.parseCCEdgeFile(fname)
  #sys.stdout.write ('Converting to single graph. ') 
  #sys.stdout.flush()
  g = parse_cc_graph.toSinglegraph(g)
  ga = make_draw_attribs (ga, res)
  print 'Done loading graph.'
  return (g, ga, res)


file_name = args[0]

(g, ga, res) = loadGraph(file_name)


# pre-pruning

#split_neighbor(g, ga, 'nsJSEventListener', 3)
prune_info_parent_edges(g, ga)
if options.prune_garbage:
  prune_garbage(g, ga)
if options.prune_js:
  prune_js(g, ga)
if options.prune_non_js:
  prune_non_js (g, ga)
if options.prune_marked_js:
  prune_marked_js(g, ga)
#prune_js_listener(g, ga)
#prune_no_childs(g)


gg = split_graph(g)


analyze_graphs()



# print out graphs

outf = open(file_name + '.dot', 'w')


# print out stats at the start of a file

outf.write('// ')
for x, v in sorted(size_counts.iteritems()):
  outf.write('{0}={1}({2}), '.format(x, v, x * v))
outf.write('\n')

# number of nodes the CC collected
outf.write('// num nodes collected is ')
outf.write('{0}\n'.format(len(res[1] - set(ga.gcNodes.keys()))))
  # should we count JS nodes as garbage here?

# number of JS roots
#outf.write('// num of JS roots is {0}\n'.format(len(ga.roots & ga.black_gced)))



outf.write('digraph graph_name {\n')

# don't print more than 100 of each size of other graph
size_counts = {}

for x in other_graphs:
  if should_print_graph(x[1], ga, 1):
    print_graph(outf, x[1], ga)

#for x in other_graphs:
#  if x[0] != 10 and x[0] != 36:
#    continue
#  #if should_print_graph(x[1], ga):
#  c = size_counts.get(x[0], 0)
#  if c < 20:
#    size_counts[x[0]] = c + 1
#    print_graph(outf, x[1], ga)

print_solo_graphs(outf, solo_graphs, ga)
print_pair_graphs(outf, pair_graphs, ga)
print_tri_graphs(outf, tri_graphs, ga)
print_death_stars(outf, death_stars, ga)

outf.write('}\n')
outf.close()


exit(0)

############



outf.write('// ')
for x, v in sorted(size_counts.iteritems()):
  outf.write('{0}={1}({2}), '.format(x, v, x * v))
outf.write('\n')

# number of nodes the CC collected
outf.write('// num nodes collected is ')
outf.write('{0}\n'.format(len(graph_nodes(g) - ga.black_rced - ga.black_gced)))

# number of JS roots
outf.write('// num of JS roots is {0}\n'.format(len(ga.roots & ga.black_gced)))





