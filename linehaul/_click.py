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
import functools
import inspect

import click


async def kill_all(loop, timeout=None):
    tasks = [
        t for t in asyncio.Task.all_tasks(loop=loop)
        if t is not asyncio.Task.current_task(loop=loop)
    ]

    for task in tasks:
        task.cancel()

    return await asyncio.wait(tasks, timeout=timeout)


class AsyncCommand(click.Command):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Check to see if the callback is a coroutine function, and if it is
        # we'll wrap it so that it gets called with the global event loop.
        if (inspect.iscoroutinefunction(self.callback)
                or inspect.iscoroutinefunction(
                    getattr(self.callback, "__wrapped__", None))):
            original_callback = self.callback

            @functools.wraps(original_callback)
            def wrapper(*args, **kwargs):
                loop = asyncio.get_event_loop()
                coro = original_callback(*args, **kwargs)
                future = asyncio.ensure_future(coro, loop=loop)

                try:
                    return loop.run_until_complete(future)
                except KeyboardInterrupt:
                    future.cancel()
                    loop.run_until_complete(future)
                    loop.run_until_complete(kill_all(loop))

            self.callback = wrapper

    def make_context(self, *args, **kwargs):
        ctx = super().make_context(*args, **kwargs)
        ctx.event_loop = asyncio.get_event_loop()
        return ctx
