# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import json
import urllib.parse

import asks

from linehaul.bigquery.oauth2 import ServiceApplicationClient, TokenExpiredError
from linehaul.logging import SPEW as log_SPEW


GOOGLE_AUDIENCE = "https://www.googleapis.com/oauth2/v4/token"
GOOGLE_TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"

BIGQUERY_SCOPE = "https://www.googleapis.com/auth/bigquery"


logger = logging.getLogger(__name__)


class TokenFetchError(Exception):
    def __init__(self, *args, status_code, body, **kwargs):
        super().__init__(*args, **kwargs)

        self.status_code = status_code
        self.body = body


class BigQueryError(Exception):
    def __init__(self, *args, status_code, body, **kwargs):
        super().__init__(*args, **kwargs)

        self.status_code = status_code
        self.body = body


class _BigQueryAuthentication:
    def __init__(self, session, account, private_key):
        self._session = session
        self._client = ServiceApplicationClient(
            client_id=account,
            private_key=private_key,
            audience=GOOGLE_AUDIENCE,
            issuer=account,
        )

    async def get_token(self):
        logger.debug("Fetching OAuth2 token from %r", GOOGLE_TOKEN_URL)

        url, headers, body, = self._client.prepare_token_request(
            GOOGLE_TOKEN_URL, scope=BIGQUERY_SCOPE
        )

        resp = await self._session.post(url, headers=headers, data=body)

        if resp.status_code != 200:
            raise TokenFetchError(
                f"Invalid Response Code: {resp.status_code} with body: {resp.text!r}",
                status_code=resp.status_code,
                body=resp.text,
            )

        logger.debug("Saving fetched OAuth2 token.")
        self._client.parse_request_body_response(resp.text)

    async def authenticate(self, url, *args, **kwargs):
        logger.log(log_SPEW, "Authenticating request for %r", url)

        if not self._client.access_token:
            await self.get_token()

        try:
            return self._client.add_token(url, *args, **kwargs)
        except TokenExpiredError:
            logger.debug("OAuth2 token expired.")
            await self.get_token()
            return self._client.add_token(url, *args, **kwargs)


class BigQuery:

    _base_location = "https://www.googleapis.com"

    def __init__(self, account, private_key, *args, max_connections=None, **kwargs):
        super().__init__(*args, **kwargs)

        if max_connections is None:
            max_connections = 30

        self._session = asks.Session(connections=max_connections)
        self._auth = _BigQueryAuthentication(self._session, account, private_key)

    def _make_url(self, path):
        return urllib.parse.urljoin(self._base_location, path)

    async def get_schema(self, target):
        project_id, dataset_id, table_id = target.split(".")
        path = (
            f"/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/"
            f"tables/{table_id}"
        )
        url = self._make_url(path)
        url, headers, body = await self._auth.authenticate(url, http_method="GET")

        resp = await self._session.get(url, headers=headers, data=body)

        if resp.status_code != 200:
            raise BigQueryError(
                f"Invalid Response Code: {resp.status_code} with body: {resp.text!r}",
                status_code=resp.status_code,
                body=resp.text,
            )

        return resp.json().get("schema", {}).get("fields", [])

    async def update_schema(self, target, schema):
        project_id, dataset_id, table_id = target.split(".")
        path = (
            f"/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/"
            f"tables/{table_id}"
        )
        url = self._make_url(path)
        headers = {"Content-Type": "application/json"}
        body = json.dumps({"schema": {"fields": schema}})
        url, headers, body = await self._auth.authenticate(
            url, http_method="PATCH", headers=headers, body=body
        )

        resp = await self._session.request("PATCH", url, headers=headers, data=body)

        if resp.status_code != 200:
            raise BigQueryError(
                f"Invalid Response Code: {resp.status_code} with body: {resp.text!r}",
                status_code=resp.status_code,
                body=resp.text,
            )

    async def insert_all(self, target, rows, template_suffix):
        data = {
            "kind": "bigquery#tableDataInsertAllRequest",
            "skipInvalidRows": True,
            "ignoreUnknownValues": True,
            "templateSuffix": template_suffix,
            "rows": rows,
        }

        project_id, dataset_id, table_id = target.split(".")
        path = (
            f"/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/"
            f"tables/{table_id}/insertAll"
        )
        url = self._make_url(path)
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data)
        url, headers, body = await self._auth.authenticate(
            url, http_method="POST", headers=headers, body=body
        )

        resp = await self._session.post(url, headers=headers, data=body)

        if resp.status_code != 200:
            raise BigQueryError(
                f"Invalid Response Code: {resp.status_code} with body: {resp.text!r}",
                status_code=resp.status_code,
                body=resp.text,
            )
