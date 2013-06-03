Analysis scripts for GC heap dumps.

parse_gc_graph.py is a library for parsing GC heap dumps.

find_roots.py produces a path from a root to an object to say why it is alive.

Unlike with the cycle collector, for the GC we can always tell why an object is alive in JS.