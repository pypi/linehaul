use std::error::Error;
use std::io::prelude::*;
use std::str;

#[macro_use]
extern crate nom;

use flate2::read::GzDecoder;
use log::{error, info, warn};

mod events;
mod syslog;

pub fn process<'a>(lines: impl Iterator<Item = &'a str>) {
    for line in lines {
        // Parse each line as a syslog message.
        let message: syslog::SyslogMessage = match line.parse() {
            Ok(m) => m,
            Err(_e) => {
                error!("Could not parse '{:?}' as a syslog message.", line);
                continue;
            }
        };

        // Parse the log entry as an event.
        let event: events::Event = match message.message.parse() {
            Ok(e) => e,
            Err(_e) => {
                error!("Could not parse '{:?}' as an event.", message.message);
                continue;
            }
        };

        info!("Event: {:?}", event);

        break;
    }
}

pub fn process_file(file: impl Read) -> Result<(), Box<dyn Error>> {
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
        });

    process(lines);

    Ok(())
}
