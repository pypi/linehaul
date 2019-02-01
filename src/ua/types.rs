use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct Installer {
    pub name: Option<String>,
    pub version: Option<String>,
}

impl Default for Installer {
    fn default() -> Self {
        Installer {
            name: None,
            version: None,
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Implementation {
    pub name: Option<String>,
    pub version: Option<String>,
}

impl Default for Implementation {
    fn default() -> Self {
        Implementation {
            name: None,
            version: None,
        }
    }
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

impl Default for Distro {
    fn default() -> Self {
        Distro {
            name: None,
            version: None,
            id: None,
            libc: None,
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct System {
    pub name: Option<String>,
    pub release: Option<String>,
}

impl Default for System {
    fn default() -> Self {
        System {
            name: None,
            release: None,
        }
    }
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

impl Default for UserAgent {
    fn default() -> Self {
        UserAgent {
            installer: None,
            python: None,
            implementation: None,
            distro: None,
            system: None,
            cpu: None,
            openssl_version: None,
            setuptools_version: None,
        }
    }
}
