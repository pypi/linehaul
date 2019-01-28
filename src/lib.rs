use std::str;

#[macro_use]
extern crate nom;

use log::{info};

mod syslog;

pub fn process<'a>(lines: impl Iterator<Item = &'a str>) {
    for line in lines {
        let message: SyslogMessage = line.parse();
        break;
    }
}
