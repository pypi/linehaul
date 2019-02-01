#[macro_export]
macro_rules! ua_parser {
    ($parser:ident, $($name:ident($pattern:expr) => |$($param:ident),*| $body:block),+) => {
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
                    let caps = re.captures(input).unwrap();
                    let func_name = &self.callbacks[match_];

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
