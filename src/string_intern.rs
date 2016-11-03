/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

use std::collections::HashMap;
use std::hash::BuildHasherDefault;
use fnv::FnvHasher;

pub type Atom = usize;

pub struct StringIntern {
    to_atom: HashMap<String, Atom, BuildHasherDefault<FnvHasher>>,
    from_atom: HashMap<Atom, String, BuildHasherDefault<FnvHasher>>,
}

impl StringIntern {
    pub fn new() -> StringIntern {
        StringIntern {
            to_atom: HashMap::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
            from_atom: HashMap::with_hasher(BuildHasherDefault::<FnvHasher>::default()),
        }
    }

    pub fn add(&mut self, s: &str) -> Atom {
        match self.to_atom.get(s) {
            Some(v) => return v.clone(),
            None => ()
        }
        let new_id = self.to_atom.len();
        assert_eq!(self.to_atom.insert(String::from(s), new_id), None);
        assert_eq!(self.from_atom.insert(new_id, String::from(s)), None);
        return new_id;
    }

    pub fn get(&self, atom: &Atom) -> &str {
        match self.from_atom.get(atom) {
            Some(s) => return s,
            None => panic!("Didn't find atom")
        }
    }
}


