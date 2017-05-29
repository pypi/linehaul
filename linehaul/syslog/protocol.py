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

from . import parser


class LineProtocol(asyncio.Protocol):

    delimiter = b"\r\n"

    def connection_made(self, transport):
        self.transport = transport
        self._buffer = b""

        return super().connection_made(transport)

    def data_received(self, data):
        # Get all of the lines of the buffer, and the new data, and then split
        # this into lines.
        lines = (self._buffer + data).split(self.delimiter)

        # The last line may not yet be complete, so we'll pop this data off of
        # our list of lines and return it to the buffer.
        self._buffer = lines.pop(-1)

        # For each line that we've be given call our line_received method with
        # the line.
        for line in lines:
            self.line_received(line)

    def line_received(self, line):
        raise NotImplementedError

    def send_line(self, line):
        self.transport.write(line + self.delimiter)


class SyslogProtocol(LineProtocol):

    delimiter = b"\n"

    def __init__(self, *args, token=None, loop=None, **kwargs):
        if token is not None:
            token = token.encode("utf8")  # We always assume utf8

        self.token = token
        self.loop = loop

        return super().__init__(*args, **kwargs)

    def line_received(self, line):
        # If we have a token, and the line we've been given doesn't start with
        # that token, then just silently drop it, otherwise we'll strip the
        # token from the start of the line.
        if self.token is not None:
            if not line.startswith(self.token):
                return
            else:
                line = line[len(self.token):]

        # We're going to just assume that all of our lines are valid UTF8 lines
        try:
            line = line.decode("utf8")
        except UnicodeDecodeError:
            # In this case we were not given a valid UTF8 line, we're just
            # going to skip this line. It would be nice for this to be more
            # robust, but that would involve parsing using bytes the whole way
            # through and I don't really feel like that buys us much.
            return

        # If we've been given a blank link, then we'll just skip it:
        if not line:
            return

        # Actually parse our message and get a SyslogMessage object
        message = parser.parse(line)

        # Dispatch our message so that subclasses can handle them.
        self.message_received(message)

    def message_received(self, message):
        raise NotImplementedError
