use regex::{Regex, RegexSet};
use serde::{Deserialize, Serialize};
use serde_json;

#[derive(Debug, Serialize, Deserialize)]
pub struct Installer {
    pub name: Option<String>,
    pub verison: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Implementation {
    pub name: Option<String>,
    pub version: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LibC {
    pub lib: Option<String>,
    pub version: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Distro {
    pub name: Option<String>,
    pub version: Option<String>,
    pub id: Option<String>,
    pub libc: Option<LibC>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct System {
    pub name: Option<String>,
    pub release: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UserAgent {
    pub installer: Option<Installer>,
    pub python: Option<String>,
    pub implementation: Option<Implementation>,
    pub distro: Option<Distro>,
    pub system: Option<System>,
    pub cpu: Option<String>,
    pub openssl_version: Option<String>,
    pub setuptools_version: Option<String>,
}

static PATTERNS: &[(&str, fn(&Regex, &str) -> Option<UserAgent>)] =
    &[(r"^pip/\S+\s+(?P<data>.+)$", parse_pip6)];

lazy_static! {
    static ref RE: RegexSet = RegexSet::new(PATTERNS.iter().map(|i| i.0)).unwrap();
    static ref RES: Vec<Regex> = PATTERNS.iter().map(|i| Regex::new(i.0).unwrap()).collect();
}

fn parse_pip6(re: &Regex, input: &str) -> Option<UserAgent> {
    let caps = re.captures(input).unwrap();
    let parsed = serde_json::from_str::<UserAgent>(&caps["data"]);

    match parsed {
        Ok(ua) => Some(ua),
        Err(_e) => None,
    }
}

pub fn parse(input: &str) -> Option<UserAgent> {
    for match_ in RE.matches(input).iter() {
        let func = PATTERNS.iter().nth(match_).unwrap().1;
        let re = RES.iter().nth(match_).unwrap();

        match func(re, input) {
            Some(ua) => return Some(ua),
            None => continue,
        }
    }

    None
}
