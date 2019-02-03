use std::env;
use std::error::Error;
use std::fs::File;

fn main() -> Result<(), Box<dyn Error>> {
    let logger = linehaul::default_logger(linehaul::LogStyle::Readable);
    let filename = env::args().nth(1).unwrap();
    let file = File::open(filename)?;

    linehaul::process_reader(&logger, file)?;

    Ok(())
}
