use std::env;
use std::error::Error;
use std::fs::File;

use slog_scope;

fn main() -> Result<(), Box<dyn Error>> {
    let logger = linehaul::default_logger(linehaul::LogStyle::Readable);
    let _guard = slog_scope::set_global_logger(logger);
    let filename = env::args().nth(1).unwrap();
    let file = File::open(filename)?;

    linehaul::process_reader(file)?;

    Ok(())
}
