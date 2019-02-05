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
use slog::{error, o, trace, warn, Drain, Logger};
use slog_async;
use slog_envlogger;
use slog_scope::scope as log_scope;
use slog_term;
use uuid::Uuid;

mod bigquery;
mod events;
mod syslog;
mod ua;
mod utils;

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

fn parse_syslog(logger: &Logger, line: &str) -> Option<syslog::SyslogMessage> {
    match log_scope(logger, || line.parse()) {
        Ok(m) => Some(m),
        Err(_e) => {
            error!(logger, "could not parse as syslog message");
            None
        }
    }
}

fn process_event(logger: &Logger, raw_event: &str) -> Option<events::Event> {
    match log_scope(logger, || raw_event.parse()) {
        Ok(e) => Some(e),
        Err(e) => {
            match e {
                events::EventParseError::IgnoredUserAgent => {
                    trace!(logger, "skipping for ignored user agent");
                }
                events::EventParseError::InvalidUserAgent => {
                    trace!(logger, "skipping for invalid user agent");
                }
                events::EventParseError::Error => {
                    error!(logger, "invalid event");
                }
            };

            None
        }
    }
}

pub fn process<'a>(logger: &Logger, bq: &mut BigQuery, lines: impl Iterator<Item = &'a str>) {
    let events = lines
        // iterate over the lines, and turn them all in pairs of (logger, parsed msg).
        // This lets us pass the created logger into the *next* phase of the pipeline.
        .filter_map(|line| {
            let logger = logger.new(o!("syslog_raw" => line.to_string()));
            parse_syslog(&logger, line).and_then(|m| Some((logger, m)))
        })
        // Turn each parsed syslog messge into a parsed event.
        .filter_map(|(logger, m)| {
            let logger = logger.new(o!("event_raw" => m.message.clone()));
            process_event(&logger, m.message.as_ref())
        });

    for batch in events.peekable().batching(|it| match it.peek() {
        Some(_i) => Some(it.take(BATCH_SIZE).collect()),
        None => None,
    }) {
        let logger = logger.new(o!("batch_id" => Uuid::new_v4().to_string()));
        let batch: Vec<events::Event> = batch;
        let batch = batch
            .iter()
            .map(|i| match i {
                events::Event::SimpleRequest(e) => e,
            })
            .collect();

        if let Err(e) = bq.insert(&logger, batch) {
            error!(logger, "error saving batch to BigQuery"; "error" => e.to_string());
        }
    }
}

pub fn process_reader(
    logger: &Logger,
    bq: &mut BigQuery,
    file: impl Read,
) -> Result<(), Box<dyn Error>> {
    let mut gz = GzDecoder::new(file);
    let mut buffer = Vec::new();

    gz.read_to_end(&mut buffer)?;

    let lines = buffer
        .split(|c| c == &b'\n')
        .filter_map(|line| match str::from_utf8(line) {
            Ok(l) => Some(l),
            Err(e) => {
                warn!(logger, "skipping invalid line";
                      "line" => String::from_utf8_lossy(line).as_ref(),
                      "error" => e.to_string());
                None
            }
        })
        .filter(|i| !i.is_empty());

    process(logger, bq, lines);

    Ok(())
}
