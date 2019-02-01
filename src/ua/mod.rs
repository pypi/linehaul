use regex::{Regex, RegexSet};
use serde_json;

pub use types::{Distro, Implementation, Installer, LibC, System, UserAgent};

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
    },

    pip1_4(concat!(r"^pip/(?P<version>\S+) (?P<impl_name>\S+)/(?P<impl_version>\S+) ",
                   r"(?P<system_name>\S+)/(?P<system_release>\S+)$")) => |version,
                                                                          impl_name,
                                                                          impl_version,
                                                                          system_name,
                                                                          system_release| {
        let installer = Installer {
            name: Some("pip".to_string()),
            version: Some(version.to_string()),
        };
        let implementation = Implementation {
            name: match impl_name.to_string().to_lowercase().as_ref() {
                "unknown" => None,
                _ => Some(impl_name.to_string()),
            },
            version: match impl_version.to_string().to_lowercase().as_ref() {
                "unknown" => None,
                _ => Some(impl_version.to_string()),
            },
        };
        let system = System {
            name: match system_name.to_string().to_lowercase().as_ref() {
                "unknown" => None,
                _ => Some(system_name.to_string()),
            },
            release: match system_release.to_string().to_lowercase().as_ref() {
                "unknown" => None,
                _ => Some(system_release.to_string()),
            },
        };
        let python = match &implementation.name {
            Some(s) => match s.to_lowercase().as_ref() {
                "cpython" => Some(impl_version.to_string()),
                _ => None,
            },
            None => None,
        };

        Some(
            UserAgent {
                installer: Some(installer),
                implementation: Some(implementation),
                system: Some(system),
                python: python,
                distro: None,
                cpu: None,
                openssl_version: None,
                setuptools_version: None,
            }
        )
    }
);

pub fn parse(input: &str) -> Option<UserAgent> {
    PARSER.parse(input)
}
