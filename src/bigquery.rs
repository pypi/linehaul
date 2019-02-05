use std::error::Error;
use std::io::Read;

use hyper;
use hyper::header::{Authorization, Bearer, ContentType};
use hyper::mime::{Mime, SubLevel, TopLevel};
use hyper_native_tls;
use serde::{Deserialize, Serialize};
use serde_json as json;
use slog::{slog_debug, slog_warn};
use slog_scope::{debug, warn};
use url;
use uuid::Uuid;
use yup_oauth2::{GetToken, ServiceAccountAccess, ServiceAccountKey};

const BIGQUERY_URL: &str = "https://www.googleapis.com/bigquery/v2/";
const BIGQUERY_SCOPES: [&str; 1] = ["https://www.googleapis.com/auth/bigquery"];

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
            BigQueryTable {
                project: project.to_string(),
                dataset: dataset.to_string(),
                table: table.to_string(),
            }
        } else {
            panic!("nope");
        };

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

    pub fn insert<T: Serialize>(&mut self, events: Vec<T>) -> Result<(), Box<dyn Error>> {
        let rows: Vec<Row> = events
            .iter()
            .map(|item| Row {
                insert_id: Uuid::new_v4().to_string(),
                json: json::value::RawValue::from_string(json::to_string(item).unwrap()).unwrap(),
            })
            .collect();

        retry!(self.do_insert(&rows))?;

        Ok(())
    }

    fn do_insert(&mut self, rows: &[Row]) -> Result<(), Box<dyn Error>> {
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

        let token = self.auth.token(&BIGQUERY_SCOPES)?;
        let mut resp = match self
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
        {
            Ok(r) => r,
            Err(e) => match e {
                hyper::Error::Io(e) => panic!("one"),
                hyper::Error::Ssl(e) => panic!("two"),
                hyper::Error::Utf8(e) => panic!("three"),
                _ => panic!("four"),
            },
        };

        let resp = match resp.status {
            hyper::status::StatusCode::Ok => {
                let mut body = String::new();
                match resp.read_to_string(&mut body) {
                    Ok(_o) => {}
                    Err(_e) => panic!("Another?"),
                };
                match json::from_str::<TableInsertResponse>(&body) {
                    Ok(p) => p,
                    Err(_e) => panic!("wat!"),
                }
            }
            _ => {
                warn!("unexpected status code from BigQuery"; "status_code" => resp.status.to_string());
                panic!("five");
            }
        };

        debug!("inserted batch into bigquery";
               "batch_size" => batch_size,
               "errors" => resp.insert_errors.map_or(0, |e| e.len()));

        Ok(())
    }
}
