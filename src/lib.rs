use std::env;
use std::error::Error;
use std::io;
use std::io::prelude::*;
use std::str;

#[macro_use]
extern crate lazy_static;

#[macro_use]
extern crate nom;

use flate2::read::GzDecoder;
use itertools::Itertools;
use slog;
use slog::{o, slog_error, slog_trace, slog_warn, Drain};
use slog_async;
use slog_envlogger;
use slog_scope;
use slog_scope::{error, trace, warn};
use slog_term;

mod bigquery;
mod events;
mod syslog;
mod ua;

pub use bigquery::BigQuery;

#[allow(dead_code)]
pub mod build_info {
    include!(concat!(env!("OUT_DIR"), "/built.rs"));
}

const BATCH_SIZE: usize = 500;

pub enum LogStyle {
    JSON,
    Readable,
}

pub fn default_logger(style: LogStyle) -> slog::Logger {
    let level = match env::var("LINEHAUL_LOG") {
        Ok(s) => s.to_string(),
        Err(_e) => "debug".to_string(),
    };
    let kv = o!("version" => build_info::PKG_VERSION, "commit" => build_info::GIT_VERSION);

    match style {
        LogStyle::JSON => {
            let drain = slog_bunyan::default(io::stdout()).fuse();
            let drain = slog_envlogger::LogBuilder::new(drain)
                .parse(level.as_ref())
                .build();
            let drain = slog_async::Async::new(drain).build().fuse();

            slog::Logger::root(drain, kv)
        }
        LogStyle::Readable => {
            let decorator = slog_term::TermDecorator::new().stdout().build();
            let drain = slog_term::CompactFormat::new(decorator).build().fuse();
            let drain = slog_envlogger::LogBuilder::new(drain)
                .parse(level.as_ref())
                .build();
            let drain = slog_async::Async::new(drain).build().fuse();

            slog::Logger::root(drain, kv)
        }
    }
}

fn parse_syslog(line: &str) -> Option<syslog::SyslogMessage> {
    match line.parse() {
        Ok(m) => Some(m),
        Err(_e) => {
            error!("could not parse as syslog message");
            None
        }
    }
}

fn process_event(raw_event: &str) -> Option<events::Event> {
    match raw_event.parse::<events::Event>() {
        Ok(e) => Some(e),
        Err(e) => {
            match e {
                events::EventParseError::IgnoredUserAgent => {
                    trace!("skipping for ignored user agent");
                }
                events::EventParseError::InvalidUserAgent => {
                    trace!("skipping for invalid user agent");
                }
                events::EventParseError::Error => {
                    error!("invalid event");
                }
            };

            None
        }
    }
}

pub fn process<'a>(bq: &mut BigQuery, lines: impl Iterator<Item = &'a str>) {
    let messages = lines.filter_map(|line| {
        slog_scope::scope(
            &slog_scope::logger().new(o!("line" => line.to_string())),
            || parse_syslog(line),
        )
    });
    let events = messages.filter_map(|msg| {
        slog_scope::scope(
            &slog_scope::logger().new(o!("raw_event" => msg.message.clone())),
            || process_event(msg.message.as_ref()),
        )
    });

    for batch in events.peekable().batching(|it| match it.peek() {
        Some(_i) => Some(it.take(BATCH_SIZE).collect()),
        None => None,
    }) {
        let batch: Vec<events::Event> = batch;
        let batch = batch
            .iter()
            .map(|i| match i {
                events::Event::SimpleRequest(e) => e,
            })
            .collect();

        // TODO: Wrap in slog_scope.
        if let Err(e) = bq.insert(batch) {
            error!("error saving batch to BigQuery"; "error" => e.to_string());
        }
    }
}

pub fn process_reader(bq: &mut BigQuery, file: impl Read) -> Result<(), Box<dyn Error>> {
    let mut gz = GzDecoder::new(file);
    let mut buffer = Vec::new();

    gz.read_to_end(&mut buffer)?;

    let lines = buffer
        .split(|c| c == &b'\n')
        .filter_map(|line| match str::from_utf8(line) {
            Ok(l) => Some(l),
            Err(e) => {
                warn!("skipping invalid line";
                      "line" => String::from_utf8_lossy(line).as_ref(),
                      "error" => e.to_string());
                None
            }
        })
        .filter(|i| !i.is_empty());

    process(bq, lines);

    Ok(())
}
