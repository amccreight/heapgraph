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
/*
    weak_map: Addr,
    key: Addr,
    key_delegate: Addr,
    value: Addr
*/
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

impl EdgeInfo {
    fn new(addr: Addr, label: Atom) -> EdgeInfo {
        EdgeInfo { addr: addr, label: label }
    }
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
    pub fn new(node_type: NodeType, label: Atom) -> GraphNode {
        GraphNode { node_type: node_type, label: label, edges: Vec::new() }
    }
}

pub type AddrHashSet = HashSet<Addr, BuildHasherDefault<FnvHasher>>;

pub struct CCLog {
    pub nodes: HashMap<Addr, GraphNode, BuildHasherDefault<FnvHasher>>,
    pub weak_map_entries: Vec<WeakMapEntry>,
    // XXX Need to actually parse incremental root entries.
    pub incr_roots: AddrHashSet,
    atoms: StringIntern,
    // XXX Should tracking address formatting (eg win vs Linux).
    pub garbage: AddrHashSet,
    pub known_edges: HashMap<Addr, u64, BuildHasherDefault<FnvHasher>>,
}


enum ParsedLine {
    Node(Addr, GraphNode),
    Edge(EdgeInfo),
    WeakMap(Addr, Addr, Addr, Addr),
    Comment,
    Separator,
    Garbage(Addr),
    KnownEdge(Addr, u64),
}

lazy_static! {
    static ref WEAK_MAP_RE: Regex = Regex::new(r"^WeakMapEntry map=(?:0x)?([:xdigit:]+|\(nil\)) key=(?:0x)?([:xdigit:]+|\(nil\)) keyDelegate=(?:0x)?([:xdigit:]+|\(nil\)) value=(?:0x)?([:xdigit:]+)\r?").unwrap();
    static ref EDGE_RE: Regex = Regex::new(r"^> (?:0x)?([:xdigit:]+) ([^\r\n]*)\r?").unwrap();
    static ref NODE_RE: Regex = Regex::new(r"^(?:0x)?([:xdigit:]+) \[(rc=[0-9]+|gc(?:.marked)?)\] ([^\r\n]*)\r?").unwrap();
    static ref COMMENT_RE: Regex = Regex::new(r"^#").unwrap();
    static ref SEPARATOR_RE: Regex = Regex::new(r"^==========").unwrap();
    static ref RESULT_RE: Regex = Regex::new(r"^(?:0x)?([:xdigit:]+) \[([a-z0-9=]+)\]\w*").unwrap();
    static ref GARBAGE_RE: Regex = Regex::new(r"garbage").unwrap();
    static ref KNOWN_RE: Regex = Regex::new(r"^known=(\d+)").unwrap();
}

impl CCLog {
    fn new() -> CCLog {
        CCLog {
            nodes: HashMap::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            weak_map_entries: Vec::new(),
            incr_roots: HashSet::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            atoms: StringIntern::new(),
            garbage: HashSet::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            known_edges: HashMap::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
        }
    }

    pub fn atomize_addr(addr_str: &str) -> Addr {
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
                node.edges.shrink_to_fit();
                assert!(self.nodes.insert(addr, node).is_none());
            },
            None => ()
        }
    }

    fn atomize_weakmap_addr(x: &str) -> Addr {
        if x == "(nil)" {
            CCLog::atomize_addr("0")
        } else {
            CCLog::atomize_addr(&x)
        }
    }

    fn parse_line(atoms: &mut StringIntern, line: &str) -> ParsedLine {
        for caps in EDGE_RE.captures(&line).iter() {
            let addr = CCLog::atomize_addr(caps.at(1).unwrap());
            let label = atoms.add(caps.at(2).unwrap());
            return ParsedLine::Edge(EdgeInfo::new(addr, label));
        }
        for caps in NODE_RE.captures(&line).iter() {
            let addr = CCLog::atomize_addr(caps.at(1).unwrap());
            let ty = NodeType::new(caps.at(2).unwrap());
            let label = atoms.add(caps.at(3).unwrap());
            return ParsedLine::Node(addr, GraphNode::new(ty, label));
        }
        for caps in RESULT_RE.captures(&line).iter() {
            let obj = CCLog::atomize_addr(caps.at(1).unwrap());
            let tag = caps.at(2).unwrap();
            if GARBAGE_RE.is_match(&tag) {
                return ParsedLine::Garbage(obj)
            } else {
                for caps in KNOWN_RE.captures(tag) {
                    // XXX Comments say that 0x0 is in the
                    // results sometimes. Is this still true?
                    let count = u64::from_str(caps.at(1).unwrap()).unwrap();
                    return ParsedLine::KnownEdge(obj, count)
                }
                panic!("Error: Unknown result entry type: {}", tag)
            }
        }
        for caps in WEAK_MAP_RE.captures(&line).iter() {
            let map = CCLog::atomize_weakmap_addr(caps.at(1).unwrap());
            let key = CCLog::atomize_weakmap_addr(caps.at(2).unwrap());
            let delegate = CCLog::atomize_weakmap_addr(caps.at(3).unwrap());
            let val = CCLog::atomize_weakmap_addr(caps.at(4).unwrap());
            return ParsedLine::WeakMap(map, key, delegate, val);
        }
        if COMMENT_RE.is_match(&line) {
            return ParsedLine::Comment;
        }
        if SEPARATOR_RE.is_match(&line) {
            return ParsedLine::Separator;
        }
        panic!("Unknown line {}", line);
    }

    pub fn parse(f: File) -> CCLog {
        let reader = BufReader::new(f);
        let mut cc_graph = CCLog::new();
        let mut curr_node = None;

        let mut atoms = StringIntern::new();

        for pl in reader.lines().map(|l|CCLog::parse_line(&mut atoms, l.as_ref().unwrap())) {
            match pl {
                ParsedLine::Node(addr, n) => {
                    cc_graph.add_node(curr_node);
                    curr_node = Some ((addr, n));
                },
                ParsedLine::Edge(e) => curr_node.as_mut().unwrap().1.edges.push(e),
                ParsedLine::WeakMap(map, key, delegate, val) => {
                },
                ParsedLine::Comment => (),
                ParsedLine::Separator => {
                    cc_graph.add_node(curr_node);
                    curr_node = None;
                },
                ParsedLine::Garbage(obj) => assert!(cc_graph.garbage.insert(obj)),
                ParsedLine::KnownEdge(obj, rc) => assert!(cc_graph.known_edges.insert(obj, rc).is_none()),
            }
        }

        cc_graph.atoms = atoms;
        cc_graph
    }
}
