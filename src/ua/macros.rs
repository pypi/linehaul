#[macro_export]
macro_rules! ua_parser {
    ($parser:ident, $($name:ident($pattern:expr) => |$re:ident, $input:ident| $body:block),+) => {
        struct $parser {
            regex: RegexSet,
            regexes: Vec<Regex>,
            callbacks: Vec<String>,
        }

        impl $parser {
            fn new() -> $parser {
                println!("new");
                let patterns = vec![$($pattern),*];
                let regex = RegexSet::new(&patterns).unwrap();
                let regexes: Vec<Regex> = patterns.iter().map(|p| Regex::new(p).unwrap()).collect();
                let callbacks = vec![$(String::from(stringify!($name))),*];

                $parser{regex, regexes, callbacks}
            }

            fn parse(&self, input: &str) -> Option<UserAgent> {
                for match_ in self.regex.matches(input).iter() {
                    let re = &self.regexes[match_];
                    let func_name = &self.callbacks[match_];
                    let parsed = match func_name.as_ref() {
                        $(stringify!($name) => $parser::$name(re, input)),*,
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

            $(fn $name($re: &Regex, $input: &str) -> Option<UserAgent> $body),*
        }
    };
}
