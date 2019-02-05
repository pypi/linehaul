#![allow(clippy::double_comparisons)]
use std::error;
use std::fmt;
use std::str;

use chrono::{DateTime, TimeZone, Utc};
use nom::{delimited, digit, rest, take_until, take_while_m_n};

#[derive(Debug, Clone)]
pub struct InvalidFacility;

impl fmt::Display for InvalidFacility {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "invalid value for Facility")
    }
}

impl error::Error for InvalidFacility {
    fn description(&self) -> &str {
        "invalid value for Facility"
    }

    fn cause(&self) -> Option<&error::Error> {
        None
    }
}

#[derive(Debug)]
pub enum Facility {
    Kernel,
    User,
    Mail,
    Daemon,
    Auth,
    Syslog,
    LPR,
    News,
    UUCP,
    Clock,
    AuthPriv,
    FTP,
    NTP,
    Audit,
    Alert,
    Cron,
    Local0,
    Local1,
    Local2,
    Local3,
    Local4,
    Local5,
    Local6,
    Local7,
}

impl Facility {
    pub fn from_u8(int: u8) -> Result<Facility, InvalidFacility> {
        match int {
            0 => Ok(Facility::Kernel),
            1 => Ok(Facility::User),
            2 => Ok(Facility::Mail),
            3 => Ok(Facility::Daemon),
            4 => Ok(Facility::Auth),
            5 => Ok(Facility::Syslog),
            6 => Ok(Facility::LPR),
            7 => Ok(Facility::News),
            8 => Ok(Facility::UUCP),
            9 => Ok(Facility::Clock),
            10 => Ok(Facility::AuthPriv),
            11 => Ok(Facility::FTP),
            12 => Ok(Facility::NTP),
            13 => Ok(Facility::Audit),
            14 => Ok(Facility::Alert),
            15 => Ok(Facility::Cron),
            16 => Ok(Facility::Local0),
            17 => Ok(Facility::Local1),
            18 => Ok(Facility::Local2),
            19 => Ok(Facility::Local3),
            20 => Ok(Facility::Local4),
            21 => Ok(Facility::Local5),
            22 => Ok(Facility::Local6),
            23 => Ok(Facility::Local7),
            _ => Err(InvalidFacility {}),
        }
    }
}

#[derive(Debug, Clone)]
pub struct InvalidSeverity;

impl fmt::Display for InvalidSeverity {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "invalid value for Severity")
    }
}

impl error::Error for InvalidSeverity {
    fn description(&self) -> &str {
        "invalid value for Severity"
    }

    fn cause(&self) -> Option<&error::Error> {
        None
    }
}

#[derive(Debug)]
pub enum Severity {
    Emergency,
    Alert,
    Critical,
    Error,
    Warning,
    Notice,
    Informational,
    Debug,
}

impl Severity {
    pub fn from_u8(int: u8) -> Result<Severity, InvalidSeverity> {
        match int {
            0 => Ok(Severity::Emergency),
            1 => Ok(Severity::Alert),
            2 => Ok(Severity::Critical),
            3 => Ok(Severity::Error),
            4 => Ok(Severity::Warning),
            5 => Ok(Severity::Notice),
            6 => Ok(Severity::Informational),
            7 => Ok(Severity::Debug),
            _ => Err(InvalidSeverity {}),
        }
    }
}

#[derive(Debug)]
pub struct SyslogMessage {
    pub facility: Facility,
    pub severity: Severity,
    pub timestamp: DateTime<Utc>,
    pub hostname: Option<String>,
    pub appname: String,
    pub procid: Option<String>,
    pub message: String,
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
    alt!(nil_str | map!(take_until!(" "), Some))
);

named!(appname <&str, &str>, take_until!("["));

named!(procid <&str, Option<&str>>,
    alt!(nil_str | map!(take_until!("]"), Some))
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
            let facility = Facility::from_u8(priority / 8).unwrap();
            let severity = Severity::from_u8(priority - ((priority / 8) * 8)).unwrap();
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
