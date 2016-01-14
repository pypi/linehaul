#!/usr/bin/env python3.5
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

import json

import arrow
import aiohttp

from oauthlib.oauth2.rfc6749.errors import TokenExpiredError

from ._oauth2 import ServiceApplicationClient


GOOGLE_AUDIENCE = "https://www.googleapis.com/oauth2/v4/token"
GOOGLE_TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"

BIGQUERY_SCOPE = "https://www.googleapis.com/auth/bigquery"

STREAMING_URL = (
    "https://www.googleapis.com/bigquery/v2/projects/{project_id}/"
    "datasets/{dataset_id}/tables/{table_id}/insertAll"
)


class BigQueryEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, arrow.Arrow):
            return obj.float_timestamp

        return super().default(obj)


class _BigQueryClientSession:

    def __init__(self, client):
        self.client = client
        self.session = aiohttp.ClientSession()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.session.close()

    async def _get_token(self):
        url, headers, body, = self.client.oauth2.prepare_token_request(
            GOOGLE_TOKEN_URL,
            scope=BIGQUERY_SCOPE,
        )

        async with self.session.post(url, headers=headers, data=body) as resp:
            assert resp.status == 200  # TODO: Better Error Handling
            self.client.oauth2.parse_request_body_response(await resp.text())

    async def _add_token(self, *args, **kwargs):
        if not self.client.oauth2.access_token:
            await self._get_token()

        try:
            return self.client.oauth2.add_token(*args, **kwargs)
        except TokenExpiredError:
            await self._get_token()
            return self.client.oauth2.add_token(*args, **kwargs)

    async def insert_all(self, rows, template_suffix=None,
                         skip_invalid_rows=False):
        data = {
            "kind": "bigquery#tableDataInsertAllRequest",
            "rows": rows,
        }

        if template_suffix is not None:
            data["templateSuffix"] = template_suffix

        if skip_invalid_rows:
            data["skipInvalidRows"] = True

        url, headers, body = await self._add_token(
            STREAMING_URL.format(
                project_id=self.client.project_id,
                dataset_id=self.client.dataset,
                table_id=self.client.table,
            ),
            http_method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(data, cls=BigQueryEncoder),
        )

        async with self.session.post(url, headers=headers, data=body) as resp:
            assert resp.status == 200  # TODO: Better Error Handling
            data = await resp.json()

        assert data["kind"] == "bigquery#tableDataInsertAllResponse"

        for error in data.get("insertErrors", []):
            print((rows[error["index"]], error["errors"]))


class BigQueryClient:

    def __init__(self, project_id, dataset, table, client_id=None, key=None):
        self.project_id = project_id
        self.dataset = dataset
        self.table = table

        self.oauth2 = ServiceApplicationClient(
            client_id,
            key,
            audience=GOOGLE_AUDIENCE,
            issuer=client_id,
        )

    def __repr__(self):
        return (
            "<BigQueryClient project_id={!r} dataset={!r} "
            "table={!r}>"
        ).format(self.project_id, self.dataset, self.table)

    def __call__(self):
        return _BigQueryClientSession(client=self)
