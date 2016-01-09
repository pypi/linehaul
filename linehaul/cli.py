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
from .core import handle_syslog
from .syslog.protocol import SyslogProtocol


@click.command(cls=AsyncCommand)
@click.option("--bind", default="0.0.0.0")
@click.option("--port", type=int, default=512)
@click.option("--token")
@click.pass_context
async def main(ctx, bind, port, token):
    protocol = SyslogProtocol(handle_syslog, token=token, loop=ctx.event_loop)
    server = await ctx.event_loop.create_server(protocol, bind, port)

    cancelled = False
    try:
        return await server.wait_closed()
    except asyncio.CancelledError:
        click.echo(click.style("Shutting Down...", fg="yellow"))
        cancelled = True

        # Signal for the server close.
        server.close()

        # Wait until the server is closed
        await server.wait_closed()
    finally:
        # Get all of the other tasks besides the current task (which should be
        # the task that is running this coroutine).
        tasks = [
            t for t in asyncio.Task.all_tasks(loop=ctx.event_loop)
            if t is not asyncio.Task.current_task(loop=ctx.event_loop)
        ]

        # Wait for any existing tasks to finish, if we were cancelled we'll
        # only wait 30 seconds before triggering all of them to be cancelled
        # otherwise we'll just wait.
        if tasks:
            _, pending = await asyncio.wait(
                tasks,
                timeout=30 if cancelled else None,
                loop=ctx.event_loop,
            )

            for task in pending:
                task.cancel()
