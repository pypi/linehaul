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
        // TODO: To match the implementation of the Python parser, we would have to
        //       check that the pip version is >= 6... however that's a bit tricky
        //       here because Rust doesn't have anything that implements PEP 440. I
        //       think it might be pointless to do though, because if it's not pip 6+
        //       then serde will fail to deserialize and we should move onto the next.
        match serde_json::from_str::<UserAgent>(data) {
            Ok(ua) => Some(ua),
            Err(_e) => None,
        }
    }
);

pub fn parse(input: &str) -> Option<UserAgent> {
    PARSER.parse(input)
}
