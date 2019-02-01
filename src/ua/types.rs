use serde::{Deserialize, Serialize};

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
