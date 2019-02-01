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
                   r"(?P<system_name>\S+)/(?P<system_release>\S+)$"))
            => |version, impl_name, impl_version, system_name, system_release| {

        let python = match lower!(impl_name) {
            "cpython" => sval(impl_version),
            _ => None,
        };

        user_agent!(
            installer: installer!("pip", version),
            implementation: implementation!(
                name: without_unknown!(impl_name),
                version: without_unknown!(impl_version),
            ),
            system: system!(
                name: without_unknown!(system_name),
                release: without_unknown!(system_release),
            ),
            python: python,
        )
    },

    distribute(r"^Python-urllib/(?P<python>\d\.\d) distribute/(?P<version>\S+)$")
            => |python, version| {
        user_agent!(
            installer: installer!("distribute", version),
            python: sval(python),
        )
    },

    setuptools(
        r"^Python-urllib/(?P<python>\d\.\d) setuptools/(?P<version>\S+)$",
        r"^setuptools/(?P<version>\S+) Python-urllib/(?P<python>\d\.\d)$",
    ) => |version, python| {
        user_agent!(
            installer: installer!("setuptools", version),
            python: sval(python),
        )
    },

    pex(r"pex/(?P<version>\S+)$") => |version| {
        user_agent!(installer: installer!("pex", version))
    },

    conda(r"^conda/(?P<version>\S+)(?: .+)?$") => |version| {
        user_agent!(installer: installer!("conda", version))
    },

    bazel(r"^Bazel/(?:release\s+)?(?P<version>.+)$") => |version| {
        user_agent!(installer: installer!("Bazel", version))
    },

    bandersnatch(r"^bandersnatch/(?P<version>\S+) \(.+\)$") => |version| {
        user_agent!(installer: installer!("bandersnatch", version))
    },

    devpi(r"devpi-server/(?P<version>\S+) \(.+\)$") => |version| {
        user_agent!(installer: installer!("devpi", version))
    },

    z3c_pypimirror(r"^z3c\.pypimirror/(?P<version>\S+)$") => |version| {
        user_agent!(installer: installer!("z3c.pypimirror", version))
    },

    artifactory(r"^Artifactory/(?P<version>\S+)$") => |version| {
        user_agent!(installer: installer!("Artifactory", version))
    },

    nexus(r"^Nexus/(?P<version>\S+)") => |version| {
        user_agent!(installer: installer!("Nexus", version))
    },

    pep381client(r"^pep381client(?:-proxy)?/(?P<version>\S+)$") => |version| {
        user_agent!(installer: installer!("pep381client", version))
    },

    homebrew(concat!(r"^Homebrew/(?P<version>\S+) ",
                     r"\(Macintosh; Intel (?:Mac OS X|macOS) (?P<osx_version>[^)]+)\)(?: .+)?$"))
            => |version, osx_version| {
        user_agent!(
            installer: installer!("Homebrew", version),
            distro: distro!(name: sval("OS X"), version: sval(osx_version)),
        )
    },

    os(
        r"^fetch libfetch/\S+$",
        r"^libfetch/\S+$",
        r"^OpenBSD ftp$",
        r"^MacPorts/?",
        r"^NetBSD-ftp/",
        r"^slapt-get",
        r"^pypi-install/",
        r"^slackrepo$",
        r"^PTXdist",
        r"^GARstow/",
        r"^xbps/",
    ) => |,| {  // TODO: Figure out how to allow || instead of |,|
        user_agent!(installer: installer!("OS"))
    },
);

pub fn parse(input: &str) -> Option<UserAgent> {
    PARSER.parse(input)
}

fn sval(s: &str) -> Option<String> {
    Some(s.to_string())
}
