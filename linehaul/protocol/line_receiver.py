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


class BufferTooLargeError(Exception):
    pass


class TruncatedLineError(Exception):
    def __init__(self, *args, line, **kwargs):
        super().__init__(*args, **kwargs)

        self.line = line


class LineReceiver:
    def __init__(self, callback, *args, max_line_size=None, **kwargs):
        super().__init__(*args, **kwargs)

        if max_line_size is None:
            max_line_size = 16384

        self._callback = callback
        self._buffer = bytearray()
        self._searched = 0
        self._max_line_size = max_line_size

    def receive_data(self, data):
        self._buffer += data

        if len(self._buffer) > self._max_line_size:
            raise BufferTooLargeError

        lines = []
        while True:
            try:
                found = self._buffer.index(b"\n", self._searched)
            except ValueError:
                self._searched = len(self._buffer)
                break
            else:
                line = self._callback(self._buffer[: found + 1])
                if line is not None:
                    lines.append(line)
                del self._buffer[: found + 1]
                self._searched = 0

        return lines

    def close(self):
        if len(self._buffer):
            raise TruncatedLineError(
                "Left over data in buffer.", line=bytes(self._buffer)
            )
