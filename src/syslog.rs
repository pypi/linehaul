use std::str;

use chrono::{DateTime, TimeZone, Utc};
use nom::{delimited, digit, rest, take_until, take_while_m_n};
use num_derive::{FromPrimitive, ToPrimitive};
use num_traits::{FromPrimitive, ToPrimitive};

#[derive(Debug, FromPrimitive, ToPrimitive)]
enum Facility {
    Kernel = 0,
    User = 1,
    Mail = 2,
    Daemon = 3,
    Auth = 4,
    Syslog = 5,
    LPR = 6,
    News = 7,
    UUCP = 8,
    Clock = 9,
    AuthPriv = 10,
    FTP = 11,
    NTP = 12,
    Audit = 13,
    Alert = 14,
    Cron = 15,
    Local0 = 16,
    Local1 = 17,
    Local2 = 18,
    Local3 = 19,
    Local4 = 20,
    Local5 = 21,
    Local6 = 22,
    Local7 = 23,
}

#[derive(Debug, FromPrimitive, ToPrimitive)]
enum Severity {
    Emergency = 0,
    Alert = 1,
    Critical = 2,
    Error = 3,
    Warning = 4,
    Notice = 5,
    Informational = 6,
    Debug = 7,
}

#[derive(Debug)]
pub struct SyslogMessage {
    facility: Facility,
    severity: Severity,
    timestamp: DateTime<Utc>,
    hostname: Option<String>,
    appname: String,
    procid: Option<String>,
    message: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SyslogParseError(());

impl str::FromStr for SyslogMessage {
    type Err = SyslogParseError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match parse(s) {
            Ok(p) => Ok(p.1),
            Err(_e) => Err(SyslogParseError(())),
        }
    }
}

named!(uint8 <&str, u8>,
    // TODO: Handle overflows in a better way, ideally by only matching 0-255.
    map!(digit, |i| { i.parse::<u8>().unwrap() })
);

named!(nil_str <&str, Option<&str>>, do_parse!(tag!("-") >> (None)));

named!(year_date_part <&str, i32>,
    map!(take_while_m_n!(4, 4, |c: char| c.is_digit(10)), |i| i.parse::<i32>().unwrap() )
);

named!(two_digit_date_part <&str, u32>,
    map!(take_while_m_n!(2, 2, |c: char| c.is_digit(10)), |i| i.parse::<u32>().unwrap() )
);

named!(iso8601 <&str, DateTime<Utc>>,
    do_parse!(
       year:     year_date_part
    >>           tag!("-")
    >> month:    two_digit_date_part
    >>           tag!("-")
    >> day:      two_digit_date_part
    >>           tag!("T")
    >> hour:     two_digit_date_part
    >>           tag!(":")
    >> minute:   two_digit_date_part
    >>           tag!(":")
    >> seconds:  two_digit_date_part
    >>           tag!("Z")  // TODO: Support other timezones.
    >>         (Utc.ymd(year, month, day).and_hms(hour, minute, seconds))
    )
);

named!(hostname <&str, Option<&str>>,
    alt!(nil_str | map!(take_until!(" "), |i| Some(i)))
);

named!(appname <&str, &str>, take_until!("["));

named!(procid <&str, Option<&str>>,
    alt!(nil_str | map!(take_until!("]"), |i| Some(i)))
);

named!(parse <&str, SyslogMessage>,
    do_parse!(
                  tag!("<")
    >> priority:  uint8
    >>            tag!(">")
    >> timestamp: iso8601
    >>            tag!(" ")
    >> hostname:  hostname
    >>            tag!(" ")
    >> appname:   appname
    >> procid:    delimited!(tag!("["), procid, tag!("]"))
    >>            tag!(": ")
    >> message:   complete!(rest)
    >> ({
            let facility: Facility = FromPrimitive::from_u8(priority / 8).unwrap();
            let severity: Severity = FromPrimitive::from_u8(priority - (ToPrimitive::to_u8(&facility).unwrap() * 8)).unwrap();
            let hostname = match hostname {
                Some(h) => Some(h.to_string()),
                None => None,
            };
            let appname = appname.to_string();
            let procid = match procid {
                Some(id) => Some(id.to_string()),
                None => None,
            };
            let message = message.to_string();

            SyslogMessage{facility, severity, timestamp, hostname, appname, procid, message}
        })
    )
);
