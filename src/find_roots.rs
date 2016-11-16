/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

use std::collections::HashMap;
use std::collections::vec_deque::VecDeque;
use std::hash::BuildHasherDefault;
use fnv::FnvHasher;

use cc_log::CCLog;
use cc_log::Addr;
use cc_log::GraphNode;
use cc_log::NodeType;
use cc_log::EdgeInfo;


fn print_node(log: &CCLog, node: &Addr) {
    // XXX Should also support Windows-formatted addresses.
    let label = log.node_label(node).unwrap();
    print!("{:x} [{}]", node, label);
}


fn print_edge(log: &CCLog, x: &Addr, y: &Addr) {
    print!("--[{}]-->",
           &log.nodes.get(x).unwrap()
           .edges.iter()
           .filter(|e| &e.addr == y)
           .map(|e| log.atom_string(&e.label))
           .collect::<Vec<String>>()
           .join(", "));
}


fn print_known_edges(log: &CCLog, root: Addr) {
  if not knownEdges:
    return

  print '    known edges:'
  for e in knownEdges:
    print '       ',
    print_node(ga, e)
    print ' ',
    print_edge(args, ga, e, x)
    sys.stdout.write (' {0}\n'.format(x))
}


fn explain_root(log: &CCLog, root: Addr) {
    print!("    Root {:x} ", root);

    match log.nodes.get(&root).unwrap().node_type {
        NodeType::GC(true) => {
            println!("is a marked GC object.");
            if log.incr_roots.contains(&root) {
                println!("    It is an incremental root, which means it was touched during an incremental CC.");
            }
        },
        NodeType::GC(false) => panic!("Node {:x} was a root, but was not marked.", root),
        NodeType::RefCounted(rc) => {
            let num_unknown =
                if let Some(known_rc) = log.known_edges.get(&root) {
                    rc - known_rc
                } else {
                    assert!(log.incr_roots.contains(&root));
                    0
                };

            println!("is a ref counted object with {} unknown edge{}.",
                     num_unknown, if num_unknown == 1 { "" } else { "s" });

            // XXX Fix this
            //printKnownEdges(args, knownEdgesFn(root), ga, root)

            if log.incr_roots.contains(&root) {
                println!("    It is an incremental root, which means it was touched during an incremental CC.");
            }
        }
    }
}


fn print_path(log: &CCLog, path: &Vec<Addr>) {
    print_node(log, path.first().unwrap());
    println!("");
    let mut prev = path.first().unwrap();

    for p in path.split_first().unwrap().1 {
        print!("    ");
        print_edge(log, prev, p);
        print!(" ");
        print_node(log, p);
        println!("");
        prev = p;
    }

    println!("");

    explain_root(log, path[0]);
    println!("");
}

pub fn find_roots(log: &mut CCLog, target: Addr) {
    let mut work_list = VecDeque::new();
    // XXX Not setting the initial capacity makes this method about 10 times slower.
    let mut distances = HashMap::with_capacity_and_hasher(log.nodes.len(),
                                                          BuildHasherDefault::<FnvHasher>::default());
    let mut limit = -1;

    // XXX Ignore weak maps for now. See find_roots.py for how that
    // should work.

    println!("Building graph start.");

    // Create a fake start object that points to the roots and add it
    // to the graph.
    let start_addr : Addr = 1;
    assert!(!log.nodes.contains_key(&start_addr),
            "Fake object already exists in the graph");
    let mut start_node = GraphNode::new(NodeType::GC(false), log.atomize_label("START_NODE"));
    let empty_label = log.atomize_label("");
    for r in log.known_edges.keys()
        .chain(log.incr_roots.iter())
        .chain(log.nodes.iter()
               .filter(|&(_, gn)| match gn.node_type { NodeType::GC(b) => b, _ => false })
               .map(|(x, _)| x)) {
        start_node.edges.push(EdgeInfo { addr:r.clone(), label: empty_label.clone() });
    }
    assert!(log.nodes.insert(start_addr, start_node).is_none());
    assert!(distances.insert(start_addr, (-1, None)).is_none());
    work_list.push_back(start_addr);

    println!("Searching graph.");

    // Search the graph.
    while !work_list.is_empty() {
        let x = work_list.pop_front().unwrap();
        let dist = distances.get(&x).as_mut().unwrap().0;

        assert!(dist >= limit, "work_list should see nodes in increasing distance order");
        limit = dist;

        if x == target {
            // Found target: nothing to do?
            // This will just find the shortest path to the object.
            continue;
        }

        let x_node = match log.nodes.get(&x) {
            Some(n) => n,
            None => panic!("missing node: {:x}", x),
        };

        let new_dist = dist + 1;
        let new_dist_node = (new_dist, Some(x));
        for e in &x_node.edges {
            let y = &e.addr;
            match &distances.get(y) {
                &Some(&(y_dist, _)) => assert!(y_dist <= new_dist),
                &None => {
                    distances.insert(y.clone(), new_dist_node.clone());
                    work_list.push_back(y.clone());
                }
            }
        }
    }

    // Print out the paths by unwinding backwards to generate a path,
    // then print the path.
    println!("Printing results.");
    let mut print_work_list = VecDeque::new();
    print_work_list.push_back(target);

    while !print_work_list.is_empty() {
        let mut p = print_work_list.pop_front().unwrap();
        let mut path = Vec::new();
        while distances.contains_key(&p) {
            path.push(p.clone());
            match distances.get(&p).unwrap().1 {
                Some(next_p) => p = next_p,
                None => break
            };
        }

        if path.is_empty() {
            println!("Didn't find a path.");
            println!("");
            // XXX print information about known edges.
        } else {
            assert_eq!(path.last(), Some(&start_addr));

            path.pop();
            path.reverse();

            print_path(&log, &path);
        }
    }

}
