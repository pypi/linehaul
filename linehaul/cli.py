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

import importlib_resources
import itertools
import json
import uuid

from typing import Optional

import asks
import arrow
import attr
import cattr
import click
import trio

from linehaul.bigquery import BigQuery
from linehaul.events import parser as _event_parser
from linehaul.migration import migrate as _migrate
from linehaul.protocol import LineReceiver
from linehaul.syslog import parser as _syslog_parser


asks.init("trio")


_cattr = cattr.Converter()
_cattr.register_unstructure_hook(arrow.Arrow, lambda o: o.float_timestamp)


@attr.s(auto_attribs=True, slots=True, frozen=True)
class LinehaulParser:

    token: Optional[str] = None

    def __call__(self, line: bytes) -> Optional[_event_parser.Download]:
        line = line.decode("utf8")

        # Check our token, and remove it from the start of the line if it matches.
        if self.token is not None:
            # TODO: Use a Constant Time Compare?
            if not line.startswith(self.token):
                return
            line = line[len(self.token) :]

        # Parse the incoming Syslog Message, and get the download event out of it.
        try:
            msg = _syslog_parser.parse(line)
            event = _event_parser.parse(msg.message)
        except ValueError:
            # TODO: Better Error Logging.
            return

        return event


@attr.s(auto_attribs=True, slots=True, frozen=True)
class LinehaulHandler:

    _incoming: trio.Queue
    token: Optional[str] = None

    async def __call__(self, stream):
        lr = LineReceiver(LinehaulParser(token=self.token))
        while True:
            try:
                data: bytes = await stream.receive_some(1024)
            except trio.BrokenStreamError:
                data = b""

            if not data:
                lr.close()
                break

            for msg in lr.recieve_data(data):
                await self._incoming.put(msg)


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


async def _serve(
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
            trio.serve_tcp, LinehaulHandler(incoming, token=token), port
        )

        task_status.started()


@click.group(context_settings={"auto_envvar_prefix": "LINEHAUL"})
def cli():
    pass


@cli.command()
@click.option("--bind", default="0.0.0.0")
@click.option("--port", type=int, default=512)
@click.option("--token")
@click.option("--credentials", type=click.File("r", encoding="utf8"), required=True)
@click.argument("table")
def serve(bind, port, token, credentials, table):
    credentials = json.load(credentials)
    bq = BigQuery(credentials["client_email"], credentials["private_key"])
    trio.run(
        _serve,
        bq,
        table,
        bind,
        port,
        token,
        restrict_keyboard_interrupt_to_checkpoints=True,
    )


@cli.command()
@click.option("--credentials", type=click.File("r", encoding="utf8"), required=True)
@click.argument("table")
def migrate(credentials, table):
    credentials = json.load(credentials)
    bq = BigQuery(credentials["client_email"], credentials["private_key"])
    schema = json.loads(importlib_resources.read_text("linehaul", "schema.json"))
    trio.run(_migrate, bq, table, schema)
