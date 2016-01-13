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


class Server:

    def __init__(self, *args, loop=None, **kwargs):
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._args = args
        self._kwargs = kwargs

    async def __aenter__(self):
        self._server = await self._loop.create_server(
            *self._args,
            **self._kwargs,
        )
        return self._server

    async def __aexit__(self, exc_type, exc, tb):
        if self._server.sockets is not None:
            self._server.close()
            await self._server.wait_closed()
