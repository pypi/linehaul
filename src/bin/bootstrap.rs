use std::error::Error;
use std::io::Read;

use aws_lambda_events::event::s3::{S3Event, S3EventRecord};
use aws_lambda_events::event::sqs::SqsEvent;
use flate2::read::GzDecoder;
use lambda_runtime::{error::HandlerError, lambda, Context};
use log::error;
use rusoto_core::Region;
use rusoto_s3::{DeleteObjectRequest, GetObjectRequest, S3Client, S3};
use serde_json;
use simple_logger;

fn process_event(event: &S3EventRecord) -> Result<(), Box<dyn Error>> {
    let region = event
        .aws_region
        .as_ref()
        .ok_or("No region specified.".to_owned())?
        .parse::<Region>()?;
    // TODO: Cache our clients by region, so we don't have to constantly
    //       reopen new connections.
    let client = S3Client::new(region);

    let bucket = event
        .s3
        .bucket
        .name
        .as_ref()
        .ok_or("No bucket specified.".to_owned())?
        .to_string();
    let key = event
        .s3
        .object
        .key
        .as_ref()
        .ok_or("No Key specified.".to_owned())?
        .to_string();

    let output = client
        .get_object(GetObjectRequest {
            bucket: bucket.clone(),
            key: key.clone(),
            ..Default::default()
        })
        .sync()?;

    match output.body {
        Some(b) => {
            let mut gz = GzDecoder::new(b.into_blocking_read());
            let mut contents = String::new();

            gz.read_to_string(&mut contents)?;

            linehaul::process(contents.split("\n"));

            client
                .delete_object(DeleteObjectRequest {
                    bucket,
                    key,
                    ..Default::default()
                })
                .sync()?;
        }
        None => {
            error!("No body found for {:?}, skipping deletion.", key);
        }
    }

    Ok(())
}

fn handler(e: SqsEvent, _c: Context) -> Result<(), HandlerError> {
    for message in &e.records {
        if let Some(body) = &message.body {
            let res: serde_json::Result<S3Event> = serde_json::from_str(&body);
            match res {
                Ok(e) => {
                    for event in &e.records {
                        if let Err(e) = process_event(event) {
                            error!("Could not process S3 event ({:?}: {:?}", e, event);
                        }
                    }
                }
                Err(e) => error!("Could not parse SQS Body ({:?}): {:?}", e, body),
            }
        }
    }

    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    simple_logger::init_with_level(log::Level::Info)?;

    lambda!(handler);

    Ok(())
}
