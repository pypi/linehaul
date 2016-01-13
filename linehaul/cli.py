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

import click

from ._click import AsyncCommand
from .core import Linehaul


@click.command(cls=AsyncCommand)
@click.option("--bind", default="0.0.0.0")
@click.option("--port", type=int, default=512)
@click.option("--token")
@click.pass_context
async def main(ctx, bind, port, token):
    loop = ctx.event_loop

    # Create our Linehaul object, this is a simple object which acts as a
    # factory for asyncio.Protocol instances. The key thing is that this keeps
    # track of active protocol instances so that they can be shutdown when
    # we're exiting.
    with Linehaul(token=token, loop=loop) as linehaul:
        # Start up the server listening on the bound ports.
        server = await loop.create_server(linehaul, bind, port)

        try:
            # Wait for the server to close, it's unlikely this will actually
            # happen since there is nothing to actually close it at this point.
            # However we want to block at this point until the program exits,
            # and if the server closes for some reason, we do want to continue
            # executing this coroutine.
            await server.wait_closed()
        except asyncio.CancelledError:  # TODO: Should this be more general?
            # If we were told to cancel, then the program must be exiting so
            # we'll
            # close our server to prevent it from accepting any new connections
            # and wait for that to occur.
            server.close()
            await server.wait_closed()
