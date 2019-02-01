use std::str;

use simple::parse_v3 as parse_simple_v3;
pub use simple::SimpleRequest;

mod simple;

#[derive(Debug)]
pub enum Event {
    SimpleRequest(SimpleRequest),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EventParseError {
    IgnoredUserAgent,
    Error,
}

impl str::FromStr for Event {
    type Err = EventParseError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match parse(s) {
            Ok(p) => match p.1 {
                Some(e) => Ok(e),
                None => Err(EventParseError::IgnoredUserAgent),
            },
            Err(_e) => Err(EventParseError::Error),
        }
    }
}

named!(bar <&str, &str>, tag!("|"));

named!(parse <&str, Option<Event>>,
    do_parse!(
               tag!("3@")
    >> simple: parse_simple_v3
    >> ({
            match simple {
                Some(simple) => Some(Event::SimpleRequest(simple)),
                None => None,
            }
        })
    )
);
