use std::str;

#[macro_use]
extern crate nom;

use log::{error, info};

mod syslog;

pub fn process<'a>(lines: impl Iterator<Item = &'a str>) {
    for line in lines {
        let message: syslog::SyslogMessage = match line.parse() {
            Ok(m) => { m },
            Err(_e) => {
                error!("Could not parse '{:?}' as a syslog message.", line);
                continue;
             }
        };

        break;
    }
}
