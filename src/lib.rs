use std::str;

#[macro_use]
extern crate nom;

use log::{error, info};

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
