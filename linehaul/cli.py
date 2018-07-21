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


_sentinel = object()


def validate_schema(existing, desired):
    # Loop over the existing schema, and the desired schema together, and look
    # for differences.
    for existing_item, desired_item in itertools.zip_longest(
        existing, desired, fillvalue=_sentinel
    ):
        if desired_item is _sentinel:
            raise ValueError("Cannot remove columns")
        elif existing_item is _sentinel:
            if desired_item["mode"] not in {"NULLABLE", "REPEATED"}:
                raise ValueError(
                    f"Cannot add non NULLABLE/REPEATED column "
                    f"{desired_item['name']!r} to existing schema."
                )
        else:
            if existing_item["name"] != desired_item["name"]:
                raise ValueError(
                    f"Found column named {desired_item['name']!r} in new schema when "
                    f"expected column named {existing_item['name']!r}"
                )

            if existing_item["type"] != desired_item["type"]:
                raise ValueError(
                    f"Cannot change type of column {existing_item['name']!r} from "
                    f"{existing_item['type']!r} to {desired_item['type']!r}."
                )

            if existing_item["mode"] != desired_item["mode"] and not (
                existing_item["mode"] == "REQUIRED"
                and desired_item["mode"] == "NULLABLE"
            ):
                raise ValueError(
                    f"Cannot change mode of column {existing_item['name']!r} except "
                    f"from REQUIRED to NULLABLE"
                )

            if existing_item["type"] == "RECORD":
                # Recurse into the record and validate the sub schema
                validate_schema(existing_item["fields"], desired_item["fields"])


@attr.s(auto_attribs=True, slots=True, frozen=True)
class Linehaul:

    bigquery: BigQuery
    table: str

    async def serve(
        self, bind="0.0.0.0", port=512, token=None, task_status=trio.TASK_STATUS_IGNORED
    ):
        incoming = trio.Queue(1000)
        outgoing = trio.Queue(10)  # Multiply by 500 to get total # of downloads

        async with trio.open_nursery() as nursery:
            nursery.start_soon(collector, incoming, outgoing)

            for _ in range(10):
                nursery.start_soon(sender, outgoing, self.bigquery, self.table)

            await nursery.start(
                trio.serve_tcp, LinehaulHandler(incoming, token=token), port
            )

            task_status.started()

    async def migrate(self):
        desired_schema = json.loads(
            importlib_resources.read_text("linehaul", "schema.json")
        )
        current_schema = await self.bigquery.get_schema(self.table)

        # If we do not have a schema, then we ca simply send whatever schema we have
        # set to BigQuery without worry about backwards incompatible changes.
        if current_schema is None:
            await self.bigquery.update_schema(self.table, desired_schema)
        # However, if we have an existing schema, then we need to diff it against our
        # desired schema, and ensure that all of the changes we're making are backwards
        # compatible.
        else:
            validate_schema(current_schema, desired_schema)
            await self.bigquery.update_schema(self.table, desired_schema)


pass_linehaul = click.make_pass_decorator(Linehaul)


@click.group(context_settings={"auto_envvar_prefix": "LINEHAUL"})
@click.option("--table", required=True)
@click.option("--credentials", type=click.File("r", encoding="utf8"), required=True)
@click.pass_context
def cli(ctx, table, credentials):
    credentials = json.load(credentials)

    ctx.obj = Linehaul(
        bigquery=BigQuery(credentials["client_email"], credentials["private_key"]),
        table=table,
    )


@cli.command()
@click.option("--bind", default="0.0.0.0")
@click.option("--port", type=int, default=512)
@click.option("--token")
@pass_linehaul
def serve(lh, bind, port, token):
    trio.run(
        lh.serve, bind, port, token, restrict_keyboard_interrupt_to_checkpoints=True
    )


@cli.command()
@pass_linehaul
def migrate(lh):
    trio.run(lh.migrate)
