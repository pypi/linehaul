use std::time::Duration;

use backoff;
use backoff::{ExponentialBackoff, Operation};

pub fn retry_for<F, T, E>(mut func: F, dur: Duration) -> Result<T, E>
where
    F: FnMut() -> Result<T, E>,
{
    let mut backoff = ExponentialBackoff {
        max_elapsed_time: Some(dur),
        ..Default::default()
    };

    let mut op = || Ok(func()?);

    op.retry(&mut backoff).map_err(|e| match e {
        backoff::Error::Permanent(e) | backoff::Error::Transient(e) => e,
    })
}

pub fn retry<F, T, E>(func: F) -> Result<T, E>
where
    F: FnMut() -> Result<T, E>,
{
    retry_for(func, Duration::from_secs(60))
}
