#[macro_export]
macro_rules! retry {
    ($body:expr) => {{
        use backoff::{Error, ExponentialBackoff, Operation};
        use std::time::Duration;

        let mut op = || Ok($body?);
        let mut backoff = ExponentialBackoff {
            max_elapsed_time: Some(Duration::from_secs(60)),
            ..Default::default()
        };

        op.retry(&mut backoff).map_err(|e| match e {
            Error::Permanent(e) | Error::Transient(e) => e,
        })
    }};
}
