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

from typing import Optional

import attr
import click
import trio

from linehaul.events import parser as _event_parser
from linehaul.protocol import LineReceiver
from linehaul.syslog import parser as _syslog_parser


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


async def sender(outgoing):
    while True:
        to_send = await outgoing.get()
        print(len(to_send))
        print(to_send[0])
        print("")


@attr.s(auto_attribs=True, slots=True, frozen=True)
class Linehaul:

    bind: str = "0.0.0.0"
    port: int = 512
    token: Optional[str] = None

    async def __call__(self, task_status=trio.TASK_STATUS_IGNORED):
        incoming = trio.Queue(20)
        outgoing = trio.Queue(20)

        async with trio.open_nursery() as nursery:
            nursery.start_soon(collector, incoming, outgoing)
            nursery.start_soon(sender, outgoing)

            await nursery.start(
                trio.serve_tcp, LinehaulHandler(incoming, token=self.token), self.port
            )

            task_status.started()


@click.command(context_settings={"auto_envvar_prefix": "LINEHAUL"})
@click.option("--bind", default="0.0.0.0")
@click.option("--port", type=int, default=512)
@click.option("--token")
def main(bind, port, token):
    trio.run(
        Linehaul(bind=bind, port=port, token=token),
        restrict_keyboard_interrupt_to_checkpoints=True,
    )
