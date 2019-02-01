#[macro_export]
macro_rules! ua_parser {
    ($parser:ident, $($name:ident($($pattern:expr),+ $(,)?) => |$($param:ident),* $(,)?| $body:block),+ $(,)?) => {
        use std::collections::HashMap;

        use regex::{Regex, RegexSet};

        struct $parser {
            regex: RegexSet,
            regexes: HashMap<String, Regex>,
            callbacks: HashMap<String, String>,
        }

        impl $parser {
            fn new() -> $parser {
                println!("new");
                let patterns = vec![$($($pattern),+),*];
                let regex = RegexSet::new(patterns).unwrap();
                let mut regexes = HashMap::new();
                let mut callbacks = HashMap::new();

                $($(
                    regexes.insert($pattern.to_string(), Regex::new($pattern).unwrap());
                    callbacks.insert($pattern.to_string(), String::from(stringify!($name)))
                );+);*;

                $parser{regex, regexes, callbacks}
            }

            fn parse(&self, input: &str) -> Option<UserAgent> {
                for match_ in self.regex.matches(input).iter() {
                    let re = &self.regex.patterns()[match_];
                    let func_name = &self.callbacks[re];
                    let caps = self.regexes[re].captures(input).unwrap();

                    let parsed = match func_name.as_ref() {
                        $(stringify!($name) => {
                            $parser::$name($(&caps[stringify!($param).trim_start_matches('_')]),*)
                        }),*,
                        _ => {
                            panic!("Invalid callback");
                        }
                    };

                    match parsed {
                        Some(ua) => return Some(ua),
                        None => continue,
                    };
                }

                None
            }

            $(fn $name($($param: &str),*) -> Option<UserAgent> $body)*
        }
    };
}


#[macro_export]
macro_rules! installer {
    ($name:expr) => {
        Some(Installer {name: $name, ..Default::default()()})
    };

    ($name:expr, $version:expr) => {
        Some(
            Installer {
                name: Some($name.to_string()),
                version: Some($version.to_string()),
                ..Default::default()
            }
        )
    };
}

#[macro_export]
macro_rules! distro {
    ($($name:ident : $value:expr),* $(,)?) => {
        Some(Distro { $($name: $value),*, ..Default::default() })
    };
}

#[macro_export]
macro_rules! user_agent {
    ($($name:ident : $value:expr),* $(,)?) => {
        Some(UserAgent { $($name: $value),*, ..Default::default() })
    };
}
