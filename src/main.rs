use std::fs::File;
use std::env;

#[macro_use] extern crate lazy_static;
extern crate regex;
extern crate fnv;

mod string_intern;
mod cc_log;
mod find_roots;

use cc_log::CCLog;

fn main() {
    if env::args().len() < 3 {
        println!("Need at least two arguments (file name, target object)");
        return
    }

    let file_name = env::args().nth(1).unwrap();
    let target_string = env::args().nth(2).unwrap();

    let f = match File::open(file_name) {
        Ok(file) => file,
        Err(err) => return println!("File error: {}", err),
    };

    println!("Parsing file.");
    let mut cc_log = CCLog::parse(f);
    let target = CCLog::atomize_addr(&target_string);

    println!("Finding roots.");
    find_roots::find_roots(&mut cc_log, target);
}
