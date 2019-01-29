use std::env;
use std::error::Error;
use std::fs::File;
use std::io::prelude::*;

use flate2::read::GzDecoder;
use log::info;
use simple_logger;

fn main() -> Result<(), Box<dyn Error>> {
    simple_logger::init_with_level(log::Level::Info)?;

    info!("Running");

    // Prints each argument on a separate line
    let filename = env::args().nth(1).unwrap();
    let file = File::open(filename)?;
    let mut gz = GzDecoder::new(&file);
    let mut contents = String::new();

    gz.read_to_string(&mut contents)?;

    linehaul::process(contents.split("\n"));

    Ok(())
}
