use std::fmt;
use std::collections::HashMap;
use std::collections::HashSet;
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

#[derive(PartialEq)]
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
    pub known_edges: HashMap<Addr, i32, BuildHasherDefault<FnvHasher>>,
}


enum ParsedLine {
    Node(Addr, GraphNode),
    Edge(EdgeInfo),
    WeakMap(Addr, Addr, Addr, Addr),
    IncrRoot(Addr),
    Comment,
    Separator,
    Garbage(Addr),
    KnownEdge(Addr, i32),
}

lazy_static! {
    static ref WEAK_MAP_RE: Regex = Regex::new(r"^WeakMapEntry map=(?:0x)?([:xdigit:]+|\(nil\)) key=(?:0x)?([:xdigit:]+|\(nil\)) keyDelegate=(?:0x)?([:xdigit:]+|\(nil\)) value=(?:0x)?([:xdigit:]+)\r?").unwrap();
}

fn addr_char_val(c: u8) -> u64 {
    match c {
        48...57 => u64::from(c) - 48, // digits
        97...102 => u64::from(c) - 97 + 10, // lower case a-f
        _ => panic!("invalid character {}", c as char),
    }
}

fn read_addr_val(s: &[u8]) -> (u64, usize) {
    let mut addr = 0;
    let mut chars_read = 0;
    for c in s {
        if *c == ' ' as u8 {
            break;
        }
        addr *= 16;
        addr += addr_char_val(*c);
        chars_read += 1;
    }
    (addr, chars_read)
}

fn refcount_char_val(c: u8) -> Option<i32> {
    match c {
        48...57 => Some(i32::from(c) - 48), // digits
        _ => None,
    }
}

fn read_refcount_val(s: &[u8]) -> (i32, usize) {
    let mut len = 1;
    let mut rc = refcount_char_val(s[0]).unwrap();
    while let Some(v) = refcount_char_val(s[len]) {
        rc *= 10;
        rc += v;
        len += 1;
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

fn split_addr(mut s: &[u8]) -> (Addr, usize) {
    expect_bytes(b"0x", s);
    s = &s[2..];
    let (new_addr, addr_len) = read_addr_val(&s);
    (new_addr, 2 + addr_len)
}

fn process_string_with_refcount(atoms: &mut StringIntern, chunks: &[ParseChunk], mut s: &[u8]) -> (Option<Addr>, Atom, Option<i32>) {
    let mut addr = None;
    let mut rc = None;
    for e in chunks {
        match e {
            &ParseChunk::FixedString(expected) => {
                expect_bytes(expected, s);
                s = &s[expected.len()..];
            },
            &ParseChunk::Address => {
                assert!(addr.is_none(), "Only expected one address in ParseChunk list");
                let (new_addr, addr_len) = split_addr(&s);
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

    (addr, atoms.add(from_utf8(&s).unwrap()), rc)
}

fn process_string(atoms: &mut StringIntern, chunks: &[ParseChunk], s: &[u8]) -> (Addr, Atom) {
    let (addr, lbl, rc) = process_string_with_refcount(atoms, chunks, s);
    assert!(rc.is_none());
    (addr.unwrap(), lbl)
}

fn process_string_fixed(atoms: &mut StringIntern, fixed_string: &[u8], s: &[u8]) -> Atom {
    let chunks = [ParseChunk::FixedString(fixed_string)];
    let (addr, lbl, rc) = process_string_with_refcount(atoms, &chunks, s);
    assert!(addr.is_none());
    assert!(rc.is_none());
    lbl
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
        self.nodes.get(node).map(|g| self.atom_string(&g.label))
    }

    fn add_node(&mut self, curr_node: Option<(Addr, GraphNode)>)
    {
        if let Some((addr, mut node)) = curr_node {
            node.edges.shrink_to_fit();
            assert!(self.nodes.insert(addr, node).is_none());
        }
    }

    fn atomize_weakmap_addr(x: &str) -> Addr {
        CCLog::atomize_addr(if x == "(nil)" { "0" } else { &x })
    }

    fn parse_addr_line(mut atoms: &mut StringIntern, addr: Addr, s: &[u8]) -> Option<ParsedLine> {
        match s[2] as char {
            'g' => {
                if s[3] == 'c' as u8 {
                    // [gc] or [gc.marked]
                    if s[4] == ']' as u8 {
                        let label = process_string_fixed(&mut atoms, b" [gc] ", s);
                        return Some(ParsedLine::Node(addr, GraphNode::new(NodeType::GC(false), label)));
                    } else {
                        let label = process_string_fixed(&mut atoms, b" [gc.marked] ", s);
                        return Some(ParsedLine::Node(addr, GraphNode::new(NodeType::GC(true), label)));
                    }
                }
                expect_bytes(b" [garbage]", s);
                Some(ParsedLine::Garbage(addr))
            },
            'r' => {
                // [rc=1234]
                let ps = [ParseChunk::FixedString(b" [rc="),
                          ParseChunk::RefCount, ParseChunk::FixedString(b"] ")];
                if let (None, label, Some(rc)) = process_string_with_refcount(&mut atoms, &ps, s) {
                    Some(ParsedLine::Node(addr, GraphNode::new(NodeType::RefCounted(rc), label)))
                } else {
                    None
                }
            },
            _ => {
                let ps = [ParseChunk::FixedString(b" [known="),
                          ParseChunk::RefCount, ParseChunk::FixedString(b"]")];
                if let (None, _, Some(count)) = process_string_with_refcount(&mut atoms, &ps, s) {
                    // XXX Comments say that 0x0 is in the
                    // results sometimes. Is this still true?
                    Some(ParsedLine::KnownEdge(addr, count))
                } else {
                    None
                }
            }
        }
    }

    fn parse_line(mut atoms: &mut StringIntern, line: &str) -> ParsedLine {
        let s = line.as_bytes();
        match s[0] as char {
            '>' => {
                let ps = [ParseChunk::FixedString(b"> "), ParseChunk::Address, ParseChunk::FixedString(b" ")];
                let (addr, label) = process_string(&mut atoms, &ps, s);
                ParsedLine::Edge(EdgeInfo::new(addr, label))
            },
            '#' => ParsedLine::Comment,
            'W' => {
                if let Some(caps) = WEAK_MAP_RE.captures(&line) {
                    let map = CCLog::atomize_weakmap_addr(caps.get(1).unwrap().as_str());
                    let key = CCLog::atomize_weakmap_addr(caps.get(2).unwrap().as_str());
                    let delegate = CCLog::atomize_weakmap_addr(caps.get(3).unwrap().as_str());
                    let val = CCLog::atomize_weakmap_addr(caps.get(4).unwrap().as_str());
                    ParsedLine::WeakMap(map, key, delegate, val)
                } else {
                    panic!("Invalid line starting with W: {}", line)
                }
            },
            'I' => {
                let ps = [ParseChunk::FixedString(b"IncrementalRoot "), ParseChunk::Address];
                let (addr, _) = process_string(&mut atoms, &ps, s);
                ParsedLine::IncrRoot(addr)
            },
            '=' => {
                expect_bytes(b"==========", s);
                ParsedLine::Separator
            }
            _ => {
                // All of the remaining cases start with an address.
                let (addr, addr_len) = split_addr(&s);
                if let Some(pl) = CCLog::parse_addr_line(&mut atoms, addr, &s[addr_len..]) {
                    pl
                } else {
                    panic!("Unknown line {}", line)
                }
            }
        }
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
