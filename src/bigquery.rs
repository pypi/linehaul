use std::error::Error;
use std::fmt;
use std::io::Read;

use hyper;
use hyper::header::{Authorization, Bearer, ContentType};
use hyper::mime::{Mime, SubLevel, TopLevel};
use hyper::status::{StatusClass, StatusCode};
use hyper_native_tls;
use serde::{Deserialize, Serialize};
use serde_json as json;
use slog::{debug, error, Logger};
use url;
use uuid::Uuid;
use yup_oauth2::{GetToken, ServiceAccountAccess, ServiceAccountKey};

use super::utils::retry;

const BIGQUERY_URL: &str = "https://www.googleapis.com/bigquery/v2/";
const BIGQUERY_SCOPES: [&str; 1] = ["https://www.googleapis.com/auth/bigquery"];

macro_rules! read_body {
    ($resp:ident, retryable => $retryable:expr) => {{
        let mut body = String::new();
        let result = $resp.read_to_string(&mut body).map_err(|_e| BigQueryError {
            message: "IO error reading response body".to_string(),
            status: Some($resp.status),
            body: None,
            retryable: $retryable,
        });

        match result {
            Ok(_r) => Ok(body),
            Err(e) => Err(e),
        }
    }};
    ($resp:ident) => {
        read_body!($resp, retryable => true)
    };
}

#[derive(Clone, Serialize)]
struct Row {
    #[serde(rename = "insertId")]
    insert_id: String,
    json: Box<json::value::RawValue>,
}

#[derive(Serialize)]
struct TableInsertAll {
    kind: String,

    #[serde(rename = "skipInvalidRows")]
    skip_invalid_rows: Option<bool>,

    #[serde(rename = "ignoreUnknownValues")]
    ignore_unknown_values: Option<bool>,

    #[serde(rename = "templateSuffix")]
    template_suffix: Option<String>,

    rows: Option<Vec<Row>>,
}

impl Default for TableInsertAll {
    fn default() -> TableInsertAll {
        TableInsertAll {
            kind: "bigquery#tableDataInsertAllRequest".to_string(),
            skip_invalid_rows: None,
            ignore_unknown_values: None,
            template_suffix: None,
            rows: None,
        }
    }
}

#[derive(Debug, Deserialize)]
struct TableInsertErrorInfo {
    reason: String,
    location: String,
    #[serde(rename = "debugInfo")]
    debug_info: String,
    message: String,
}

#[derive(Debug, Deserialize)]
struct TableInsertError {
    index: u16,
    errors: Vec<TableInsertErrorInfo>,
}

#[derive(Debug, Deserialize)]
struct TableInsertResponse {
    kind: String,

    #[serde(rename = "insertErrors")]
    insert_errors: Option<Vec<TableInsertError>>,
}

#[derive(Debug, Clone)]
pub struct BigQueryError {
    pub message: String,
    pub status: Option<StatusCode>,
    pub body: Option<String>,
    retryable: bool,
}

impl Default for BigQueryError {
    fn default() -> BigQueryError {
        BigQueryError {
            message: String::new(),
            status: None,
            body: None,
            retryable: true,
        }
    }
}

impl fmt::Display for BigQueryError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl Error for BigQueryError {
    fn description(&self) -> &str {
        "an error communicating with BigQuery"
    }

    fn cause(&self) -> Option<&Error> {
        None
    }
}

impl From<backoff::Error<BigQueryError>> for BigQueryError {
    fn from(e: backoff::Error<BigQueryError>) -> Self {
        match e {
            backoff::Error::Permanent(e) | backoff::Error::Transient(e) => e,
        }
    }
}

struct BigQueryTable {
    project: String,
    dataset: String,
    table: String,
}

pub struct BigQuery {
    table: BigQueryTable,
    auth: ServiceAccountAccess<hyper::Client>,
    client: hyper::Client,
    base_url: url::Url,
}

impl BigQuery {
    pub fn new(table: &str, key: &str) -> Result<BigQuery, Box<dyn Error>> {
        let split = table.split('.').collect::<Vec<&str>>();
        let table = if let [project, dataset, table] = &split[..] {
            Ok(BigQueryTable {
                project: project.to_string(),
                dataset: dataset.to_string(),
                table: table.to_string(),
            })
        } else {
            Err(format!("Could not parse: {}", table))
        }?;

        let client = hyper::Client::with_connector(hyper::net::HttpsConnector::new(
            hyper_native_tls::NativeTlsClient::new()?,
        ));
        let secret: ServiceAccountKey = json::from_str(key)?;
        let auth = ServiceAccountAccess::new(
            secret,
            hyper::Client::with_connector(hyper::net::HttpsConnector::new(
                hyper_native_tls::NativeTlsClient::new()?,
            )),
        );

        let base_url = url::Url::parse(BIGQUERY_URL)?;

        Ok(BigQuery {
            table,
            auth,
            client,
            base_url,
        })
    }

    pub fn insert<T: Serialize>(
        &mut self,
        logger: &Logger,
        events: Vec<T>,
    ) -> Result<(), BigQueryError> {
        let rows: Vec<Row> = events
            .iter()
            .map(|item| {
                Ok(Row {
                    insert_id: Uuid::new_v4().to_string(),
                    json: json::value::RawValue::from_string(json::to_string(item)?)?,
                })
            })
            .filter_map(|i: Result<Row, Box<Error>>| {
                if let Err(e) = &i {
                    error!(logger, "could not serialize event"; "error" => e.to_string());
                }

                i.ok()
            })
            .collect();

        retry(|| {
            self.do_insert(logger, &rows).map_err(|e| {
                if e.retryable {
                    backoff::Error::Transient(e)
                } else {
                    backoff::Error::Permanent(e)
                }
            })
        })
        .map_err(BigQueryError::from)
        .or_else(|e| {
            let message = e.message.clone();
            let status = e.status.and_then(|s| Some(s.to_string()));
            let body = e.body.clone();
            error!(logger, "{}", message; "status" => status, "body" => body);

            Err(e)
        })
    }

    fn do_insert(&mut self, logger: &Logger, rows: &[Row]) -> Result<(), BigQueryError> {
        let batch_size = rows.len();
        let data = TableInsertAll {
            skip_invalid_rows: Some(true),
            ignore_unknown_values: Some(true),
            rows: Some(rows.to_vec()),
            ..Default::default()
        };

        let url_path = format!(
            "projects/{}/datasets/{}/tables/{}/insertAll",
            self.table.project, self.table.dataset, self.table.table
        );
        let url = self.base_url.join(url_path.as_ref()).unwrap();
        let body = json::to_string(&data).unwrap();

        let token = self
            .auth
            .token(&BIGQUERY_SCOPES)
            .map_err(|e| BigQueryError {
                message: format!("error fetching token: {}", e.to_string()),
                ..Default::default()
            })?;
        let mut resp = self
            .client
            .post(url)
            .header(Authorization(Bearer {
                token: token.access_token,
            }))
            .header(ContentType(Mime(
                TopLevel::Application,
                SubLevel::Json,
                vec![],
            )))
            .body(&body)
            .send()
            .map_err(|e| match &e {
                hyper::Error::Method
                | hyper::Error::Version
                | hyper::Error::Status
                | hyper::Error::Header => BigQueryError {
                    message: format!("invalid {}", e.to_string()),
                    retryable: false,
                    ..Default::default()
                },
                hyper::Error::Uri(e) => BigQueryError {
                    message: format!("invalid uri: {}", e.to_string()),
                    retryable: false,
                    ..Default::default()
                },
                hyper::Error::Utf8(e) => BigQueryError {
                    message: format!("invalid data: {}", e.to_string()),
                    retryable: false,
                    ..Default::default()
                },
                hyper::Error::TooLarge => BigQueryError {
                    message: "response size too large".to_string(),
                    retryable: false,
                    ..Default::default()
                },
                hyper::Error::Io(e) => BigQueryError {
                    message: format!("i/o error occured: {}", e.to_string()),
                    ..Default::default()
                },
                hyper::Error::Ssl(e) => BigQueryError {
                    message: format!("ssl error occured: {}", e.to_string()),
                    ..Default::default()
                },
                _ => BigQueryError {
                    message: "unknown error".to_string(),
                    ..Default::default()
                },
            })?;

        let resp = match resp.status.class() {
            StatusClass::Informational => Err(BigQueryError {
                message: "unexpected 1xx response".to_string(),
                status: Some(resp.status),
                body: read_body!(resp).ok(),
                retryable: true,
            }),
            StatusClass::Success => match read_body!(resp) {
                Ok(body) => match json::from_str::<TableInsertResponse>(&body) {
                    Ok(p) => Ok(p),
                    Err(_e) => Err(BigQueryError {
                        message: "invalid json response".to_string(),
                        status: Some(resp.status),
                        body: Some(body),
                        retryable: true,
                    }),
                },
                _ => Err(BigQueryError {
                    message: "invalid response body".to_string(),
                    status: Some(resp.status),
                    body: None,
                    retryable: true,
                }),
            },
            StatusClass::Redirection => Err(BigQueryError {
                message: "unexpected redirect".to_string(),
                status: Some(resp.status),
                body: read_body!(resp).ok(),
                retryable: false,
            }),
            StatusClass::ClientError => Err(BigQueryError {
                message: "client error".to_string(),
                status: Some(resp.status),
                body: read_body!(resp).ok(),
                retryable: false,
            }),
            StatusClass::ServerError => Err(BigQueryError {
                message: "server error".to_string(),
                status: Some(resp.status),
                body: read_body!(resp).ok(),
                retryable: true,
            }),
            StatusClass::NoClass => Err(BigQueryError {
                message: "unknown status code".to_string(),
                status: Some(resp.status),
                body: read_body!(resp).ok(),
                retryable: true,
            }),
        }?;

        debug!(logger, "inserted batch into bigquery";
               "batch_size" => batch_size,
               "errors" => resp.insert_errors.map_or(0, |e| e.len()));

        Ok(())
    }
}
