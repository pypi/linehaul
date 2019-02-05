use std::error::Error;
use std::time;

use aws_lambda_events::event::s3::{S3Event, S3EventRecord};
use aws_lambda_events::event::sqs::SqsEvent;
use backoff::{Error as BackoffError, ExponentialBackoff, Operation};
use base64;
use clap::{App, Arg};
use lambda_runtime::{error::HandlerError, lambda, Context};
use rusoto_core::Region;
use rusoto_s3::{DeleteObjectRequest, GetObjectError, GetObjectRequest, S3Client, S3};
use serde_json;
use slog;
use slog::{o, slog_error, slog_warn};
use slog_scope;
use slog_scope::{error, warn};

fn process_event(bq: &mut linehaul::BigQuery, event: &S3EventRecord) -> Result<(), Box<dyn Error>> {
    let region = event
        .aws_region
        .as_ref()
        .ok_or_else(|| "No region specified.".to_owned())?
        .parse::<Region>()?;
    let bucket = event
        .s3
        .bucket
        .name
        .as_ref()
        .ok_or_else(|| "No bucket specified.".to_owned())?
        .to_string();
    let key = event
        .s3
        .object
        .key
        .as_ref()
        .ok_or_else(|| "No Key specified.".to_owned())?
        .to_string();

    slog_scope::scope(
        &slog_scope::logger().new(o!("region" => region.name().to_string(),
           "bucket" => bucket.clone(),
           "key" => key.clone())),
        || -> Result<(), Box<dyn Error>> {
            // TODO: Cache our clients by region, so we don't have to constantly
            //       reopen new connections.
            let client = S3Client::new(region);
            let mut op = || {
                let output = client
                    .get_object(GetObjectRequest {
                        bucket: bucket.clone(),
                        key: key.clone(),
                        ..Default::default()
                    })
                    .sync()
                    // We turn NoSuchKey into Permanent errors to skip the retry logic for them,
                    // however all other errors will be flagged as a transient error.
                    .map_err(|e| match &e {
                        GetObjectError::NoSuchKey(_s) => BackoffError::Permanent(e),
                        _ => BackoffError::Transient(e),
                    })?;
                Ok(output)
            };
            let mut backoff = ExponentialBackoff {
                max_elapsed_time: Some(time::Duration::from_secs(60)),
                ..Default::default()
            };
            let output =
                match op.retry_notify(&mut backoff, |err: GetObjectError, dur: time::Duration| {
                    warn!("could not fetch object from s3";
              "duration" => format!("{:?}", dur),
              "error" => err.to_string());
                }) {
                    Ok(o) => o,
                    // This gnarly chain is here to make it so errors generally get returned,
                    // however in the specific case of a GetObjectError::NoSuchKey, we will
                    // act like this function was successful.
                    Err(e) => match e {
                        BackoffError::Permanent(e) | BackoffError::Transient(e) => match e {
                            GetObjectError::NoSuchKey(_s) => return Ok(()),
                            _ => return Err(Box::new(e)),
                        },
                    },
                };

            match output.body {
                Some(b) => {
                    linehaul::process_reader(bq, b.into_blocking_read())?;

                    client
                        .delete_object(DeleteObjectRequest {
                            bucket,
                            key,
                            ..Default::default()
                        })
                        .sync()?;
                }
                None => {
                    error!("no body found");
                }
            }

            Ok(())
        },
    )
}

fn handler(e: SqsEvent, _c: Context) -> Result<(), HandlerError> {
    let matches = App::new("linehaul")
        .version(linehaul::build_info::PKG_VERSION)
        .author(linehaul::build_info::PKG_AUTHORS)
        .about(linehaul::build_info::PKG_DESCRIPTION)
        .arg(
            Arg::with_name("bigquery-credentials")
                .env("BIGQUERY_CREDENTIALS")
                .value_name("BLOB")
                .help("A Base64 encoded blob of credentials")
                .required(true)
                .takes_value(true),
        )
        .arg(
            Arg::with_name("simple-requests-table")
                .env("SIMPLE_REQUESTS_TABLE")
                .value_name("PROJECT.DATASET.TABLE")
                .help("Sets the target destination for simple request events")
                .required(true)
                .takes_value(true),
        )
        .get_matches();

    let creds = String::from_utf8(
        base64::decode_config(
            matches.value_of("bigquery-credentials").unwrap(),
            base64::URL_SAFE,
        )
        .unwrap(),
    )
    .unwrap();
    // TODO: Add this to current context.
    let simple_requests_table = matches.value_of("simple-requests-table").unwrap();
    let mut bq = linehaul::BigQuery::new(simple_requests_table, creds.as_ref()).unwrap();

    for message in &e.records {
        if let Some(body) = &message.body {
            let res: serde_json::Result<S3Event> = serde_json::from_str(&body);
            match res {
                Ok(e) => {
                    for event in &e.records {
                        if let Err(e) = process_event(&mut bq, event) {
                            error!("unable to process s3 event";
                                   "error" => e.to_string(),
                                   "event" => serde_json::to_string(event).unwrap());
                        }
                    }
                }
                Err(e) => {
                    error!("unable to parse SQS body";
                           "error" => e.to_string(),
                           "body" => body.to_string());
                }
            }
        }
    }

    Ok(())
}

fn main() {
    let logger = linehaul::default_logger(linehaul::LogStyle::JSON);
    let _guard = slog_scope::set_global_logger(logger);

    lambda!(handler)
}
