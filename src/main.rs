use std::env;
use std::error::Error;
use std::fs::File;

use simple_logger;

fn main() -> Result<(), Box<dyn Error>> {
    simple_logger::init_with_level(log::Level::Info)?;

    // Prints each argument on a separate line
    let filename = env::args().nth(1).unwrap();
    let file = File::open(filename)?;

    linehaul::process_reader(file)?;

    Ok(())
}
