use chrono::{DateTime, TimeZone, Utc};
use nom::{rest, space, take_until, take_while_m_n, Context, Err as NomErr, ErrorKind};
use serde::{Deserialize, Serialize};

use super::super::ua;

#[derive(Debug, Deserialize, Serialize)]
pub struct SimpleRequest {
    pub timestamp: DateTime<Utc>,
    pub url: String,
    pub project: String,
    pub tls_protocol: Option<String>,
    pub tls_cipher: Option<String>,
    pub country_code: String,
    pub details: ua::UserAgent,
}

named!(nulll_str <&str, Option<&str>>, do_parse!(tag!("-") >> (None)));

named!(optional_str <&str, Option<&str>>,
    map!(take_until!("|"), |i| Some(i))
);

named!(two_digit_date_part <&str, u32>,
    map!(take_while_m_n!(2, 2, |c: char| c.is_digit(10)), |i| i.parse::<u32>().unwrap() )
);

named!(year_date_part <&str, i32>,
    map!(take_while_m_n!(4, 4, |c: char| c.is_digit(10)), |i| i.parse::<i32>().unwrap() )
);

named!(bar <&str, &str>, tag!("|"));

named!(date <&str, DateTime<Utc>>,
    do_parse!(
                alt!(
                      tag!("Mon")
                    | tag!("Tue")
                    | tag!("Wed")
                    | tag!("Thu")
                    | tag!("Fri")
                    | tag!("Sat")
                    | tag!("Sun"))
    >>          tag!(",")
    >>          space
    >>  day:    two_digit_date_part
    >>          space
    >>  month:  alt!(
                      tag!("Jan")
                    | tag!("Feb")
                    | tag!("Mar")
                    | tag!("Apr")
                    | tag!("May")
                    | tag!("Jun")
                    | tag!("Jul")
                    | tag!("Aug")
                    | tag!("Sep")
                    | tag!("Oct")
                    | tag!("Nov")
                    | tag!("Dec"))
    >>          space
    >>          year: year_date_part
    >>          space
    >> hours:   two_digit_date_part
    >>          tag!(":")
    >> minutes: two_digit_date_part
    >>          tag!(":")
    >> seconds: two_digit_date_part
    >>  space
    >> tag!("GMT")
    >> ({
            let month = match month {
                "Jan" => 1,
                "Feb" => 2,
                "Mar" => 3,
                "Apr" => 4,
                "May" => 5,
                "Jun" => 6,
                "Jul" => 7,
                "Aug" => 8,
                "Sep" => 9,
                "Oct" => 10,
                "Nov" => 11,
                "Dec" => 12,
                _ => panic!("A non existant month occured: {:?}.", month),
            };

            Utc.ymd(year, month, day).and_hms(hours, minutes, seconds)
        })
    )
);

named!(pub parse_v3 <&str, Option<SimpleRequest>>,
    do_parse!(
                     tag!("simple")
    >>               bar
    >> timestamp:    date
    >>               bar
    >> country_code: take_until!("|")
    >>               bar
    >> url:          take_until!("|")
    >>               bar
    >> tls_protocol: alt!(nulll_str | optional_str)
    >>               bar
    >> tls_cipher:   alt!(nulll_str | optional_str)
    >>               bar
    >> user_agent:   complete!(rest)
    >> ({
            let country_code = country_code.to_string();
            let url = url.to_string();
            let project = match url.split('/').nth(2) {
                Some(s) => s.to_string(),
                None => panic!("Couldn't split this string")  // TODO: Real Error
            };
            let tls_protocol = match tls_protocol {
                Some(s) => Some(s.to_string()),
                None => None,
            };
            let tls_cipher = match tls_cipher {
                Some(s) => Some(s.to_string()),
                None => None,
            };

            match ua::parse(user_agent) {
                Ok(ua) => match ua {
                    Some(user_agent) => {
                        Some(SimpleRequest{timestamp, url, project, tls_protocol, tls_cipher, country_code, details: user_agent})
                    },
                    None => {
                        return Err(NomErr::Failure(Context::Code("", ErrorKind::Custom(124))));
                    },
                },
                Err(_e) => {
                    return Err(NomErr::Failure(Context::Code("", ErrorKind::Custom(123))));
                }
            }
       })
    )
);
