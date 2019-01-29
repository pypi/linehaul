use std::str;

use log::info;
use simple::parse_v3 as parse_simple_v3;
pub use simple::SimpleRequest;

mod simple;

#[derive(Debug)]
pub enum Event {
    SimpleRequest(SimpleRequest),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventParseError(());

impl str::FromStr for Event {
    type Err = EventParseError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match parse(s) {
            Ok(p) => Ok(p.1),
            Err(e) => {
                info!("{:?}", e);
                Err(EventParseError(()))
            }
        }
    }
}

named!(bar <&str, &str>, tag!("|"));

named!(parse <&str, Event>,
    do_parse!(
               tag!("3@")
    >> simple: parse_simple_v3
    >> (Event::SimpleRequest(simple))
    )
);
