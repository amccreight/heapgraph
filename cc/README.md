Cycle collector log analyzer scripts
====================================

This directory contains a number of tools for processing Firefox cycle
collector graph logs.

See this page for how to generate these logs:
  https://firefox-source-docs.mozilla.org/performance/memory/gc_and_cc_logs.html

Analysis scripts
----------------

find_roots: Explain why the cycle collector kept an object alive, by
  giving a path from any rooting objects to a particular object or
  entire class of objects.

The rest of these scripts are more experimental, and may or
may not be useful.

check_cycle_collector: Cycle collector implemented in Python.  It
  checks its results against the result of the browser's cycle
  collector.

cycle_friends: Given a garbage object, produce a list of all members
  of the strongly connected component involving that object,
  considering only nodes in the graph that are garbage.

dom_grouper: Compute the number of elements in each group of DOM,
  print out information about what document they are associated with,
  if any.

dotify: CC log visualization tool.  It converts a cycle collector
  graph dump into a .dot file that can be processed by Graphviz.  It
  provides various forms of processing of the graph, such as merging
  together identical structures, to make it easier to understand.

reverse_cc_graph: produce a reversed version of a cycle collector
  graph.

js_holders: analyze the classes of C++ objects that hold references to
  JS objects.

basic_loader: basic file that just loads a graph and quits.

live_js_count: counts the the number of JS objects held live by
  preserved wrappers.

mark_remover: remove marked objects (and results) from a CC log.


Large scale analysis tools
--------------------------

garbage_census: Give the classes of garbage objects.

live_census: Give the classes of live objects in the graph, with some
  combination of similar types (for instance, JS Objects that don't
  have the same global are combined).

parental: Get the classes that are holding onto elements of a
  particular class.

edge_counter: Get the number of fields in objects of a particular
  class.


Libraries
---------

parse_cc_graph: Log parsing library.  All other scripts are built on
  top of a log parsing library.  Takes a log file and produces a
  multigraph, a set of graph attributes (like node and edge names),
  and graph results.  This makes writing additional analyses very
  easy.

node_parse_cc_graph: Simplified version of parse_cc_graph that ignores
  edges.  This makes log parsing much faster, so it is useful if you
  don't care about the edges.

fast_parse_cc_graph.py: Variant of parse_cc_graph that doesn't use
  regexps for edges.  It also doesn't record edge names.  Twice as
  fast on some tests.  Should eventually port over some variant of
  this to parse_cc_Graph.

