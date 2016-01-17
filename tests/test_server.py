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

import pretend
import pytest

from linehaul._server import Server


class FakeServer:

    def __init__(self):
        self.sockets = []
        self.closed = False

    def close(self):
        self.sockets = None
        self.closed = True

    async def wait_closed(self):
        while not self.closed:
            asyncio.sleep(0.1)

        return True


@pytest.mark.parametrize("early_close", [True, False])
@pytest.mark.asyncio
async def test_creates_server(early_close):
    server = FakeServer()

    async def server_creator():
        return server

    loop = pretend.stub(
        create_server=pretend.call_recorder(lambda *a, **kw: server_creator())
    )

    async with Server("one", "two", foo="bar", loop=loop) as s:
        assert s is server
        assert not s.closed
        if early_close:
            s.close()
            await s.wait_closed()
            assert s.closed

    assert s.closed
