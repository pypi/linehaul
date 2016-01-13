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

import asyncio
import itertools
import weakref
import uuid

import aiohttp

from . import parser
from ._queue import CloseableFlowControlQueue
from .syslog.protocol import SyslogProtocol


BATCH_SIZE = 500
MAX_WAIT = 5 * 60  # 5 minutes
STREAMING_URL = (
    "https://www.googleapis.com/bigquery/v2/projects/{project_id}/"
    "datasets/{dataset_id}/tables/{table_id}/insertAll"
)


class LinehaulProtocol(SyslogProtocol):

    transport = None

    def _ensure_sender(self):
        if self.sender is None or self.sender.done():
            self.sender = asyncio.ensure_future(
                send(self.queue, loop=self.loop),
                loop=self.loop,
            )

    def close(self):
        if self.transport is not None:
            self.transport.close()

    def connection_made(self, transport):
        super().connection_made(transport)

        self.queue = CloseableFlowControlQueue(transport)
        self.sender = None

    def connection_lost(self, exc):
        self.queue.close()

        return super().connection_lost(exc)

    def message_received(self, message):
        self.queue.put_nowait({
            "insertId": str(uuid.uuid4()),
            "json": parser.parse(message.message).serialize(),
        })
        self._ensure_sender()


class Linehaul:

    def __init__(self, **options):
        self.options = options
        self.protocols = weakref.WeakSet()

    def __call__(self, *args, **kwargs):
        p = LinehaulProtocol(*args, **kwargs, **self.options)
        self.protocols.add(p)
        return p

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        for protocol in self.protocols:
            protocol.close()


def _extract_row_date(row):
    return row["json"]["timestamp"].format("YYYYMDDD")


async def send(queue, *, loop):
    with aiohttp.ClientSession() as session:
        # Contiue processing rows while either the queue is not closed, or the
        # queue is not empty. We want to exhaust it before finishing up.
        while not queue.closed or not queue.empty():
            all_rows = []

            while len(all_rows) < BATCH_SIZE:
                # Fetch an item off of the queue, if we have existing items in
                # our list to be processed then we don't want to wait forever,
                # prefering instead to send what we have. However if we do have
                # items we'll only wait a few minutes before giving up and
                # sending what we do have.
                try:
                    row = await asyncio.wait_for(
                        queue.get(),
                        timeout=MAX_WAIT if all_rows else None,
                        loop=loop,
                    )
                except asyncio.TimeoutError:
                    break

                # Go ahead and add the row we've pulled off the queue onto our
                # list of rows to process.
                all_rows.append(row)

            for date, rows in itertools.groupby(
                    sorted(all_rows, key=_extract_row_date),
                    _extract_row_date):
                rows = list(rows)

                s = rows[0]["json"]["timestamp"].format("YYYYMMDD")
                data = {
                    "kind": "bigquery#tableDataInsertAllRequest",
                    "templateSuffix": "_{}".format(s),
                    "rows": len(rows),
                }

                print((queue.qsize(), data))
