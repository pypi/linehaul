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

import itertools
import uuid

from functools import partial
from typing import Optional

import arrow
import cattr
import trio

from linehaul.events import parser as _event_parser
from linehaul.protocol import LineReceiver
from linehaul.syslog import parser as _syslog_parser


_cattr = cattr.Converter()
_cattr.register_unstructure_hook(arrow.Arrow, lambda o: o.float_timestamp)


def _parse_line(line: bytes, token=None) -> Optional[_event_parser.Download]:
    line = line.decode("utf8")

    # Check our token, and remove it from the start of the line if it matches.
    if token is not None:
        # TODO: Use a Constant Time Compare?
        if not line.startswith(token):
            return
        line = line[len(token) :]

    # Parse the incoming Syslog Message, and get the download event out of it.
    try:
        msg = _syslog_parser.parse(line)
        event = _event_parser.parse(msg.message)
    except ValueError:
        # TODO: Better Error Logging.
        return

    return event


async def _handle_connection(stream, q, token=None):
    lr = LineReceiver(partial(_parse_line, token=token))

    while True:
        try:
            data: bytes = await stream.receive_some(1024)
        except trio.BrokenStreamError:
            data = b""

        if not data:
            lr.close()
            break

        for msg in lr.recieve_data(data):
            await q.put(msg)


async def collector(incoming, outgoing):
    to_send = []
    while True:
        with trio.move_on_after(30):
            to_send.append(await incoming.get())
            if len(to_send) < 3:  # TODO: Change to 500
                continue

        if to_send:
            await outgoing.put(to_send)
            to_send = []


def _extract_item_date(item):
    return item.timestamp.format("YYYYMDDD")


def compute_batches(all_items):
    for date, items in itertools.groupby(
        sorted(all_items, key=_extract_item_date), _extract_item_date
    ):
        items = list(items)

        yield _extract_item_date(items[0]), [
            {"insertId": str(uuid.uuid4()), "json": row}
            for row in _cattr.unstructure(items[:1])
        ],


async def sender(outgoing, bq, table):
    while True:
        to_send = await outgoing.get()

        with trio.move_on_after(120) as cancel_scope:
            for template_suffix, batch in compute_batches(to_send):
                await bq.insert_all(table, batch, template_suffix)

        if cancel_scope.cancelled_caught:
            # TODO: Log an error that we took too long trying to send data to BigQuery
            pass


async def server(
    bq,
    table,
    bind="0.0.0.0",
    port=512,
    token=None,
    task_status=trio.TASK_STATUS_IGNORED,
):
    incoming = trio.Queue(1000)
    outgoing = trio.Queue(10)  # Multiply by 500 to get total # of downloads

    async with trio.open_nursery() as nursery:
        nursery.start_soon(collector, incoming, outgoing)

        for _ in range(10):
            nursery.start_soon(sender, outgoing, bq, table)

        await nursery.start(
            trio.serve_tcp, partial(_handle_connection, q=incoming, token=token), port
        )

        task_status.started()
