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

    def _put(self, item):
        if not self._paused and self.full():
            self._paused = True
            self._transport.pause_reading()

        return super()._put(item)

    def _get(self):
        try:
            return super()._get()
        finally:
            self._maybe_resume_transport()


class CloseableQueueMixin:

    def __init__(self, *args, **kwargs):
        self._closed = False

        super().__init__(*args, **kwargs)

    def _put(self, item):
        if self.closed:
            raise QueueClosed

        return super()._put(item)

    def _close_waiters(self, waiters):
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_exception(QueueClosed)

    @property
    def closed(self):
        return self._closed

    def close(self):
        self._closed = True
        self._close_waiters(self._getters)
        self._close_waiters(self._putters)


class FlowControlQueue(FlowControlQueueMixin, asyncio.Queue):
    pass


class CloseableFlowControlQueue(CloseableQueueMixin,
                                FlowControlQueueMixin,
                                asyncio.Queue):
    pass
