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


class QueueClosed(Exception):
    pass


class FlowControlQueueMixin:

    def __init__(self, transport, *args, maxsize=2 ** 16, **kwargs):
        self._transport = transport
        self._paused = False

        super().__init__(*args, maxsize=maxsize, **kwargs)

    def _maybe_resume_transport(self):
        if self._paused and self.qsize() <= self.maxsize:
            self._paused = False
            self._transport.resume_reading()

    def put_nowait(self, item):
        if not self._paused and self.full():
            self._paused = True
            self._transport.pause_reading()

        self._put(item)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)

    def get_nowait(self, *args, **kwargs):
        try:
            return super().get_nowait(*args, **kwargs)
        finally:
            self._maybe_resume_transport()


class CloseableQueueMixin:

    def __init__(self, *args, **kwargs):
        self._closed = False

        super().__init__(*args, **kwargs)

    @property
    def closed(self):
        return self._closed

    def close(self):
        self._closed = True

    async def put(self, item):
        if self.closed:
            raise QueueClosed

        return await super().put(item)

    def put_nowait(self, item):
        if self.closed:
            raise QueueClosed

        return super().put_nowait(item)


class FlowControlQueue(FlowControlQueueMixin, asyncio.Queue):
    pass


class CloseableFlowControlQueue(CloseableQueueMixin,
                                FlowControlQueueMixin,
                                asyncio.Queue):
    pass
