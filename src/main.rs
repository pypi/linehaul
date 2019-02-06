use std::error::Error;
use std::fs::File;
use std::io::Read;

use clap::{App, Arg, SubCommand};
use slog::{debug, o, Logger};
use slog_scope;

fn load_credentials(logger: &Logger, filename: &str) -> Result<String, Box<dyn Error>> {
    debug!(logger, "using credentials file");
    let mut creds_file = File::open(filename)?;
    let mut creds = String::new();
    creds_file.read_to_string(&mut creds)?;

    Ok(creds)
}

fn process_filename(
    logger: &Logger,
    bq: &mut linehaul::BigQuery,
    filename: &str,
) -> Result<(), Box<dyn Error>> {
    let file = File::open(filename)?;
    linehaul::process_reader(logger, bq, file)?;
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let logger = linehaul::default_logger(linehaul::LogStyle::Readable);
    let _guard = slog_scope::set_global_logger(logger.clone());

    let matches = App::new("linehaul")
        .version(linehaul::build_info::PKG_VERSION)
        .author(linehaul::build_info::PKG_AUTHORS)
        .about(linehaul::build_info::PKG_DESCRIPTION)
        .arg(
            Arg::with_name("bigquery-credentials")
                .long("bigquery-creds")
                .short("c")
                .value_name("FILE")
                .help("Sets the path to the BigQuery credentials")
                .required(true)
                .takes_value(true),
        )
        .arg(
            Arg::with_name("simple-requests-table")
                .long("st")
                .value_name("PROJECT.DATASET.TABLE")
                .help("Sets the target destination for simple request events")
                .required(true)
                .takes_value(true),
        )
        .subcommand(
            SubCommand::with_name("process")
                .about("processes a compressed log file")
                .arg(
                    Arg::with_name("input")
                        .value_name("INPUT")
                        .help("Sets the path to the compressed log file to process")
                        .required(true)
                        .takes_value(true),
                ),
        )
        .get_matches();

    let creds_filename = matches
        .value_of("bigquery-credentials")
        .unwrap()
        .to_string();
    let creds = load_credentials(
        &logger.new(o!("creds-file" => creds_filename.clone())),
        &creds_filename,
    )?;

    let simple_requests_table = matches.value_of("simple-requests-table").unwrap();
    let logger = logger.new(o!("simple_requests_table" => simple_requests_table.to_string()));

    let mut bq = linehaul::BigQuery::new(simple_requests_table, creds.as_ref());

    match matches.subcommand() {
        ("process", Some(matches)) => {
            let filename = matches.value_of("input").unwrap().to_string();
            process_filename(
                &logger.new(o!("file" => filename.clone())),
                &mut bq,
                &filename,
            )?;
        }
        _ => Err("Must have a command name")?,
    };

    Ok(())
}
