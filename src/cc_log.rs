use std::fmt;
use std::collections::HashMap;
use std::collections::HashSet;
use std::str::FromStr;
use std::io::BufRead;
use std::io::BufReader;
use std::fs::File;
use regex::Regex;
use std::hash::BuildHasherDefault;
use fnv::FnvHasher;

use string_intern::Atom;
use string_intern::StringIntern;


pub type Addr = u64;

pub struct WeakMapEntry {
    weak_map: Addr,
    key: Addr,
    key_delegate: Addr,
    value: Addr
}

pub enum NodeType {
    RefCounted(i32),
    GC(bool),
}

impl NodeType {
    fn new(s: &str) -> NodeType {
        match s.split("rc=").nth(1) {
            Some(rc_num) => NodeType::RefCounted(rc_num.parse().unwrap()),
            None => NodeType::GC(s.starts_with("gc.")),
        }
    }
}

pub struct EdgeInfo {
    pub addr: Addr,
    pub label: Atom,
}

pub struct GraphNode {
    pub node_type: NodeType,
    pub label: Atom,
    // XXX This representation doesn't do anything smart with multiple
    // edges to a single address, but maybe that's better than dealing
    // with a map.
    pub edges: Vec<EdgeInfo>,
}

impl fmt::Display for NodeType {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            NodeType::RefCounted(rc) => write!(f, "rc={}", rc),
            NodeType::GC(is_marked) => write!(f, "gc{}", if is_marked { ".marked" } else { "" }),
        }
    }
}

impl GraphNode {
    fn dump(&self) {
        print!("type: {} edges: ", self.node_type);
        for e in self.edges.iter() {
            print!("{}, ", e.addr);
        }
        println!("");
    }
}

pub type AddrHashSet = HashSet<Addr, BuildHasherDefault<FnvHasher>>;

// The argument to from_str_radix can't start with 0x, but it would be
// nice if our resulting output did contain it, as appropriate.

// XXX Don't really need to explicitly maintain this mapping. What we
// really need is something to detect the formatting (Windows or
// Linux) and then print it out in the right way.

pub struct CCGraph {
    pub nodes: HashMap<Addr, GraphNode, BuildHasherDefault<FnvHasher>>,
    pub weak_map_entries: Vec<WeakMapEntry>,
    // XXX Need to actually parse incremental root entries.
    pub incr_roots: AddrHashSet,
    atoms: StringIntern,
    // XXX Should tracking address formatting (eg win vs Linux).
}

impl CCGraph {
    fn new() -> CCGraph {
        CCGraph {
            nodes: HashMap::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            weak_map_entries: Vec::new(),
            incr_roots: HashSet::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            atoms: StringIntern::new(),
        }
    }

    pub fn atomize_addr(&mut self, addr_str: &str) -> Addr {
        match u64::from_str_radix(&addr_str, 16) {
            Ok(v) => v,
            Err(_) => {
                println!("Invalid address string: {}", addr_str);
                panic!("Invalid address string")
            }
        }
    }

    pub fn atomize_label(&mut self, label: &str) -> Atom {
        self.atoms.add(label)
    }

    pub fn atom_string(&self, a: &Atom) -> String {
        String::from(self.atoms.get(a))
    }

    pub fn node_label(&self, node: &Addr) -> Option<String> {
        match self.nodes.get(node) {
            Some(g) => Some(self.atom_string(&g.label)),
            None => None
        }
    }

    fn add_node(&mut self, curr_node: Option<(Addr, GraphNode)>)
    {
        match curr_node {
            Some((addr, mut node)) => {
                // XXX duplicate checking?
                node.edges.shrink_to_fit();
                self.nodes.insert(addr, node);
            },
            None => ()
        }
    }

    fn atomize_weakmap_addr(&mut self, x: &str) -> Addr {
        if x == "(nil)" {
            self.atomize_addr("0")
        } else {
            self.atomize_addr(&x)
        }
    }

    fn parse(reader: &mut BufReader<File>) -> CCGraph {
        let weak_map_re = Regex::new(r"^WeakMapEntry map=(?:0x)?([a-zA-Z0-9]+|\(nil\)) key=(?:0x)?([a-zA-Z0-9]+|\(nil\)) keyDelegate=(?:0x)?([a-zA-Z0-9]+|\(nil\)) value=(?:0x)?([a-zA-Z0-9]+)\r?").unwrap();
        let edge_re = Regex::new(r"^> (?:0x)?([a-zA-Z0-9]+) ([^\r\n]*)\r?").unwrap();
        let node_re = Regex::new(r"^(?:0x)?([a-zA-Z0-9]+) \[(rc=[0-9]+|gc(?:.marked)?)\] ([^\r\n]*)\r?").unwrap();
        let comment_re = Regex::new(r"^#").unwrap();
        let separator_re = Regex::new(r"^==========").unwrap();

        let mut line = String::with_capacity(1000);

        let mut cc_log = CCGraph::new();
        let mut curr_node : Option<(Addr, GraphNode)> = None;

        while reader.read_line(&mut line).unwrap_or(0) != 0 {
            match edge_re.captures(&line) {
                Some(caps) => {
                    let ref mut x = curr_node.as_mut().unwrap().1;
                    let addr = cc_log.atomize_addr(caps.at(1).unwrap());
                    let label = cc_log.atomize_label(caps.at(2).unwrap());
                    x.edges.push(EdgeInfo { addr: addr, label: label });
                },
                None =>
                    match node_re.captures(&line) {
                        Some(caps) => {
                            let addr = cc_log.atomize_addr(caps.at(1).unwrap());
                            let ty = NodeType::new(caps.at(2).unwrap());
                            let label = cc_log.atomize_label(caps.at(3).unwrap());
                            cc_log.add_node(curr_node);
                            curr_node = Some ((addr, GraphNode { node_type: ty, label: label, edges: Vec::new(), }));
                        },
                        None =>
                            match weak_map_re.captures(&line) {
                                Some(caps) => {
                                    let map = cc_log.atomize_weakmap_addr(caps.at(1).unwrap());
                                    let key = cc_log.atomize_weakmap_addr(caps.at(2).unwrap());
                                    let delegate = cc_log.atomize_weakmap_addr(caps.at(3).unwrap());
                                    let val = cc_log.atomize_weakmap_addr(caps.at(4).unwrap());
                                    cc_log.weak_map_entries.push(WeakMapEntry { weak_map: map, key: key, key_delegate: delegate, value: val });
                                },
                                None =>
                                    if comment_re.is_match(&line) {
                                        // Skip any comments.
                                    } else if separator_re.is_match(&line) {
                                        cc_log.add_node(curr_node);
                                        curr_node = None;
                                        break;
                                    } else {
                                        print!("\t\tno match for line {}", line);
                                        panic!("Unknown line");
                                    },
                            },
                    },
            }

            line.truncate(0);
        }

        assert!(curr_node.is_none(), "Failed to clear curr_node");

        return cc_log;
    }

    fn dump(&self) {
        println!("Nodes:");
        for (a, n) in self.nodes.iter() {
            print!("  {} ", a);
            n.dump();
        }
    }
}

pub struct CCResults {
    pub garbage: AddrHashSet,
    pub known_edges: HashMap<Addr, u64, BuildHasherDefault<FnvHasher>>,
}

impl CCResults {
    fn new() -> CCResults {
        CCResults {
            garbage: HashSet::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            known_edges: HashMap::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
        }
    }

    fn parse(reader: &mut BufReader<File>, cc_log: &mut CCGraph) -> CCResults {
        let result_re = Regex::new(r"^(?:0x)?([a-zA-Z0-9]+) \[([a-z0-9=]+)\]\w*").unwrap();
        let garbage_re = Regex::new(r"garbage").unwrap();
        let known_re = Regex::new(r"^known=(\d+)").unwrap();

        let mut line = String::with_capacity(1000);

        let mut results = CCResults::new();

        while reader.read_line(&mut line).unwrap_or(0) != 0 {
            match result_re.captures(&line) {
                Some(caps) => {
                    let obj = cc_log.atomize_addr(caps.at(1).unwrap());
                    let tag = caps.at(2).unwrap();
                    if garbage_re.is_match(&tag) {
                        assert!(results.garbage.insert(obj));
                    } else {
                        match known_re.captures(tag) {
                            Some(caps) => {
                                // XXX Comments say that 0x0 is in the
                                // results sometimes. Is this still true?
                                let count = u64::from_str(caps.at(1).unwrap()).unwrap();
                                assert!(results.known_edges.insert(obj, count).is_none(),
                                        "Found existing count");
                            },
                            None => println!("Error: Unknown result entry type: {}", tag)
                        }
                    }
                },
                None => print!("Error: Unknown result entry: {}", line)
            }
            line.truncate(0);
        }
        return results;
    }

    fn dump(&self) {
        print!("Garbage: ");
        for g in self.garbage.iter() {
            print!("{}, ", g);
        }
        println!("");

        print!("Known edges: ");
        for (a, rc) in self.known_edges.iter() {
            print!("({}, {}), ", a, rc);
        }
        println!("");
    }
}


pub struct CCLog {
    pub graph: CCGraph,
    pub results: CCResults,
}

impl CCLog {
    pub fn parse(f: File) -> CCLog {
        let mut reader = BufReader::new(f);
        let mut cc_log = CCGraph::parse(&mut reader);
        let cc_results = CCResults::parse(&mut reader, &mut cc_log);
        CCLog { graph: cc_log, results: cc_results }
    }

    pub fn dump(&self) {
        self.graph.dump();
        self.results.dump();
    }
}
