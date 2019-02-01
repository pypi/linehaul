use regex::{Regex, RegexSet};
use serde_json;

pub use types::{UserAgent};

#[macro_use]
mod macros;
mod types;

lazy_static! {
    static ref PARSER: UserAgentParser = UserAgentParser::new();
}

ua_parser!(
    UserAgentParser,
    pip6(r"^pip/(?P<version>\S+)\s+(?P<data>.+)$") => |_version, data| {
        match serde_json::from_str::<UserAgent>(data) {
            Ok(ua) => Some(ua),
            Err(_e) => None,
        }
    }
);

pub fn parse(input: &str) -> Option<UserAgent> {
    PARSER.parse(input)
}
