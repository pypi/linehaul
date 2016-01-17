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


async def cleanup(loop, *, timeout=None, cancel=False):
    current_task = asyncio.Task.current_task(loop=loop)
    tasks = [
        t for t in asyncio.Task.all_tasks(loop=loop)
        if t is not current_task
    ]

    if tasks:
        if cancel:
            for task in tasks:
                task.cancel()

        await asyncio.wait(tasks, timeout=timeout, loop=loop)


class AsyncCommand(click.Command):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Check to see if the callback is a coroutine function, and if it is
        # we'll wrap it so that it gets called with the global event loop.
        if (inspect.iscoroutinefunction(self.callback) or
                inspect.iscoroutinefunction(
                    getattr(self.callback, "__wrapped__", None))):
            original_callback = self.callback

            @functools.wraps(original_callback)
            def wrapper(*args, **kwargs):
                loop = asyncio.get_event_loop()
                main_t = asyncio.ensure_future(
                    original_callback(*args, **kwargs),
                    loop=loop,
                )

                try:
                    try:
                        loop.run_until_complete(main_t)
                    except KeyboardInterrupt:
                        main_t.cancel()
                        # This won't actually run forever because the call to
                        # loop.run_until_complete added a callback to the
                        # future that will stop the loop once main_t has
                        # finished and return control back to this function.
                        loop.run_forever()

                    # Try to clean up all of the tasks by waiting for any
                    # existing tasks to finish. Ideally the main function
                    # triggered everything to try and finish up and exit on
                    # it's own. However, if it hadn't then we'll cancel
                    # everything after we wait a small amount of time.
                    cleanup_t = asyncio.ensure_future(
                        cleanup(loop, timeout=15),
                        loop=loop,
                    )
                    try:
                        loop.run_until_complete(cleanup_t)
                    except KeyboardInterrupt:
                        # We got another KeyboardInterrupt while waiting on the
                        # pending tasks to finish. We'll cancel that cleanup
                        # job and let everything fall through to the final
                        # cleanup that just cancels everything.
                        cleanup_t.cancel()
                        # Like above, this will not actually run forever
                        # because of callback added to the cleanup_t task.
                        loop.run_forever()
                finally:
                    # Just cancel everything at this point, we don't want
                    # anything to still be executing once this is over.
                    loop.run_until_complete(cleanup(loop, cancel=True))
                    loop.stop()

            self.callback = wrapper

    def make_context(self, *args, **kwargs):
        ctx = super().make_context(*args, **kwargs)
        ctx.event_loop = asyncio.get_event_loop()
        return ctx
