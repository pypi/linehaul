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
import logging
import weakref
import uuid

from aiocron import crontab

from . import parser, _metrics as m
from ._queue import CloseableFlowControlQueue, QueueClosed
from .syslog.protocol import SyslogProtocol
from .user_agents import UnknownUserAgentError


BATCH_SIZE = 500
MAX_WAIT = 5 * 60  # 5 minutes


logger = logging.getLogger("linehaul")
ua_logger = logging.getLogger("linehaul.user_agents")


def _future_exception_logger(fut):
    if fut.done() and not fut.cancelled():
        exc = fut.exception()
        if exc is not None:
            logger.error(str(exc), exc_info=exc)


class LinehaulProtocol(SyslogProtocol):

    transport = None
    ensurer = None
    sender = None

    def __init__(self, *args, bigquery, **kwargs):
        self.bigquery = bigquery

        super().__init__(*args, **kwargs)

        self.ensurer = crontab(
            "* * * * * */15",
            func=self._ensure_sender,
            loop=self.loop,
        )

    async def _ensure_sender(self):
        if self.sender is None or self.sender.done():
            self.sender = asyncio.ensure_future(
                send(self.bigquery, self.queue, loop=self.loop),
                loop=self.loop,
            )
            self.sender.add_done_callback(_future_exception_logger)

    def close(self):
        if self.transport is not None:
            self.transport.close()
        if self.ensurer is not None:
            self.ensurer.stop()

    def connection_made(self, transport):
        super().connection_made(transport)

        self.queue = CloseableFlowControlQueue(transport)

    def connection_lost(self, exc):
        self.queue.close()
        self.ensurer.stop()

        return super().connection_lost(exc)

    def message_received(self, message):
        try:
            download = parser.parse(message.message)
        except UnknownUserAgentError as exc:
            ua_logger.error(
                "Unknown UserAgent: %s", str(exc),
                extra={
                    "fingerprint": ["{{ default }}", str(exc)],
                    "data": {"message": message},
                },
            )
            return
        except Exception as exc:
            logger.exception(str(exc), extra={"data": {"message": message}})
            return

        if download is not None:
            self.queue.put_nowait({
                "insertId": str(uuid.uuid4()),
                "json": download.serialize(),
            })
            m.EVENTS.inc()
            m.QUEUED.inc()


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


async def send(client, queue, *, loop):
    with client() as bq:
        # Contiue processing rows while either the queue is not closed, or the
        # queue is not empty. We want to exhaust it before finishing up.
        while not queue.closed or not queue.empty():
            all_rows = []

            while len(all_rows) < BATCH_SIZE:
                # Fetch an item off of the queue, if we have existing items in
                # our list to be processed then we don't want to wait forever,
                # prefering instead to send what we have. However if we do have
                # items we'll only wait a few minutes before giving up and
                # sending what we do have. In addition, if the queue is closed
                # then we'll just go ahead and send what we have now since a
                # closed, empty queue is never going to gain more items.
                try:
                    row = await asyncio.wait_for(
                        queue.get(),
                        timeout=MAX_WAIT if all_rows else None,
                        loop=loop,
                    )
                except (asyncio.TimeoutError, QueueClosed):
                    break

                # Go ahead and add the row we've pulled off the queue onto our
                # list of rows to process.
                all_rows.append(row)
                m.QUEUED.dec()

            for date, rows in itertools.groupby(
                    sorted(all_rows, key=_extract_row_date),
                    _extract_row_date):
                rows = list(rows)
                suffix = rows[0]["json"]["timestamp"].format("YYYYMMDD")

                await bq.insert_all(
                    rows,
                    template_suffix=suffix,
                    skip_invalid_rows=True,
                )
