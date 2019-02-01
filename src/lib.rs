use std::error::Error;
use std::io::prelude::*;
use std::str;

#[macro_use]
extern crate lazy_static;

#[macro_use]
extern crate nom;

use flate2::read::GzDecoder;
use log::{debug, error, warn};

mod events;
mod syslog;
mod ua;

pub fn process<'a>(lines: impl Iterator<Item = &'a str>) {
    for line in lines {
        // Parse each line as a syslog message.
        let message: syslog::SyslogMessage = match line.parse() {
            Ok(m) => m,
            Err(_e) => {
                error!("Could not parse {:?} as a syslog message.", line);
                continue;
            }
        };

        // Parse the log entry as an event.
        let _event: events::Event = match message.message.parse() {
            Ok(e) => e,
            Err(e) => {
                match e {
                    events::EventParseError::IgnoredUserAgent => {
                        debug!("Skipping {:?}.", message.message)
                    }
                    events::EventParseError::Error => {
                        error!("Could not parse {:?} as an event.", message.message)
                    }
                };

                continue;
            }
        };
    }
}

pub fn process_reader(file: impl Read) -> Result<(), Box<dyn Error>> {
    let mut gz = GzDecoder::new(file);
    let mut buffer = Vec::new();

    gz.read_to_end(&mut buffer)?;

    let lines = buffer
        .split(|c| c == &b'\n')
        .into_iter()
        .filter_map(|line| match str::from_utf8(line) {
            Ok(l) => Some(l),
            Err(e) => {
                warn!(
                    "Skipping invalid line: {:?} due to {:?}",
                    String::from_utf8_lossy(line),
                    e
                );
                None
            }
        })
        .filter(|i| i.len() > 0);

    process(lines);

    Ok(())
}
