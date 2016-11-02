use std::fmt;
use std::collections::HashMap;
use std::collections::HashSet;
use std::str::FromStr;
use std::str::from_utf8;
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
    IncrRoot(Addr),
    Comment,
    Separator,
    Garbage(Addr),
    KnownEdge(Addr, u64),
}

lazy_static! {
    static ref WEAK_MAP_RE: Regex = Regex::new(r"^WeakMapEntry map=(?:0x)?([:xdigit:]+|\(nil\)) key=(?:0x)?([:xdigit:]+|\(nil\)) keyDelegate=(?:0x)?([:xdigit:]+|\(nil\)) value=(?:0x)?([:xdigit:]+)\r?").unwrap();
    static ref INCR_ROOT_RE: Regex = Regex::new(r"IncrementalRoot (?:0x)?([:xdigit:]+)").unwrap();
    static ref COMMENT_RE: Regex = Regex::new(r"^#").unwrap();
    static ref SEPARATOR_RE: Regex = Regex::new(r"^==========").unwrap();
    static ref RESULT_RE: Regex = Regex::new(r"^(?:0x)?([:xdigit:]+) \[([a-z0-9=]+)\]\w*").unwrap();
    static ref GARBAGE_RE: Regex = Regex::new(r"garbage").unwrap();
    static ref KNOWN_RE: Regex = Regex::new(r"^known=(\d+)").unwrap();
}

fn addr_char_val(c: u8) -> u64 {
    match c {
        48...57 => u64::from(c) - 48,
        97...102 => u64::from(c) - 97 + 10,
        _ => panic!("invalid character {}", c as char),
    }
}

fn read_addr_val(s: &[u8]) -> (u64, usize) {
    let mut addr : u64 = addr_char_val(s[0]);
    let mut chars_read = 1;
    for j in 1..9 {
        addr *= 16;
        addr += addr_char_val(s[j]);
        chars_read += 1;
    }
    (addr, chars_read)
}

fn refcount_char_val(c: u8) -> Option<i32> {
    match c {
        48...57 => Some(i32::from(c) - 48),
        _ => None,
    }
}

fn read_refcount_val(s: &[u8]) -> (i32, usize) {
    let mut len = 1;
    let mut rc = refcount_char_val(s[0]).unwrap();
    loop {
        match refcount_char_val(s[len]) {
            Some(v) => {
                rc *= 10;
                rc += v;
                len += 1;
            },
            None => break
        }
    }
    (rc, len)
}

fn expect_bytes(expected: &[u8], s: &[u8])
{
    for (x, y) in expected.iter().zip(s) {
        assert_eq!(*x as char, *y as char, "Unexpected character");
    }
}

enum ParseChunk<'a> {
    FixedString(&'a [u8]),
    Address,
    RefCount,
}

static ADDR_LEN : usize = 9 + 2;

fn process_string_with_refcount(atoms: &mut StringIntern, chunks: &[ParseChunk], mut s: &[u8]) -> (Addr, Atom, Option<i32>) {
    let mut addr = None;
    let mut rc = None;
    for e in chunks {
        match e {
            &ParseChunk::FixedString(expected) => {
                expect_bytes(expected, &s[..expected.len()]);
                s = &s[expected.len()..];
            },
            &ParseChunk::Address => {
                assert!(addr.is_none(), "Only expected one address in ParseChunk list");

                expect_bytes(b"0x", &s[..2]);
                s = &s[2..];
                let (new_addr, addr_len) = read_addr_val(&s);
                assert_eq!(addr_len + 2, ADDR_LEN);
                addr = Some(new_addr);
                s = &s[addr_len..];
            },
            &ParseChunk::RefCount => {
                let (rc_val, rc_len) = read_refcount_val(&s);
                assert!(rc.is_none(), "Only expected one refcount in ParseChunk list");
                rc = Some(rc_val);
                s = &s[rc_len..];
            },
        }
    }

    (addr.unwrap(), atoms.add(from_utf8(&s).unwrap()), rc)
}

fn process_string(atoms: &mut StringIntern, chunks: &[ParseChunk], s: &[u8]) -> (Addr, Atom) {
    let (addr, lbl, rc) = process_string_with_refcount(atoms, chunks, s);
    assert!(rc.is_none());
    (addr, lbl)
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

    fn parse_line(mut atoms: &mut StringIntern, line: &str) -> ParsedLine {
        let s = line.as_bytes();
        if s[0] == '>' as u8 {
            let ps = [ParseChunk::FixedString(b"> "), ParseChunk::Address, ParseChunk::FixedString(b" ")];
            let (addr, label) = process_string(&mut atoms, &ps, s);
            return ParsedLine::Edge(EdgeInfo::new(addr, label));
        }
        if s[0] == '#' as u8 {
            assert!(COMMENT_RE.is_match(&line));
            return ParsedLine::Comment;
        }
        if s[0] == 'W' as u8 {
            if let Some(caps) = WEAK_MAP_RE.captures(&line) {
                let map = CCLog::atomize_weakmap_addr(caps.at(1).unwrap());
                let key = CCLog::atomize_weakmap_addr(caps.at(2).unwrap());
                let delegate = CCLog::atomize_weakmap_addr(caps.at(3).unwrap());
                let val = CCLog::atomize_weakmap_addr(caps.at(4).unwrap());
                return ParsedLine::WeakMap(map, key, delegate, val);
            }
            panic!("Invalid line starting with W: {}", line);
        }
        if s[0] == 'I' as u8 {
            if let Some(caps) = INCR_ROOT_RE.captures(&line) {
                let addr = CCLog::atomize_addr(caps.at(1).unwrap());
                return ParsedLine::IncrRoot(addr);
            }
            panic!("Invalid line starting with I: {}", line);
        }
        if s[0] == '=' as u8 {
            assert!(SEPARATOR_RE.is_match(&line));
            return ParsedLine::Separator;
        }

        // Really, want to pull an address out, and then further process the rest of the line.
        // Maybe split this into a new method.

        if s[ADDR_LEN + 2] == 'g' as u8 && s[ADDR_LEN + 3] == 'c' as u8 {
            // [gc] or [gc.marked]
            if s[ADDR_LEN + 4] == ']' as u8 {
                let ps = [ParseChunk::Address, ParseChunk::FixedString(b" [gc] ")];
                let (addr, label) = process_string(&mut atoms, &ps, s);
                return ParsedLine::Node(addr, GraphNode::new(NodeType::GC(false), label));
            } else {
                let ps = [ParseChunk::Address, ParseChunk::FixedString(b" [gc.marked] ")];
                let (addr, label) = process_string(&mut atoms, &ps, s);
                return ParsedLine::Node(addr, GraphNode::new(NodeType::GC(true), label));
            }
        } else if s[ADDR_LEN + 2] == 'r' as u8 {
            // [rc=1234]
            let ps = [ParseChunk::Address, ParseChunk::FixedString(b" [rc="),
                      ParseChunk::RefCount, ParseChunk::FixedString(b"] ")];
            let (addr, label, rc) = process_string_with_refcount(&mut atoms, &ps, s);
            return ParsedLine::Node(addr, GraphNode::new(NodeType::RefCounted(rc.unwrap()), label));
        }
        if let Some(caps) = RESULT_RE.captures(&line) {
            let obj = CCLog::atomize_addr(caps.at(1).unwrap());
            let tag = caps.at(2).unwrap();
            if GARBAGE_RE.is_match(&tag) {
                return ParsedLine::Garbage(obj)
            } else if let Some(caps) = KNOWN_RE.captures(tag) {
                // XXX Comments say that 0x0 is in the
                // results sometimes. Is this still true?
                let count = u64::from_str(caps.at(1).unwrap()).unwrap();
                return ParsedLine::KnownEdge(obj, count)
            }
            panic!("Error: Unknown result entry type: {}", tag)
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
                ParsedLine::WeakMap(_, _, _, _) => {
                },
                ParsedLine::IncrRoot(addr) => {
                    cc_graph.incr_roots.insert(addr);
                }
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
