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

import abc


class UnableToParse(Exception):
    pass


class UserAgentParser(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def test(self, ua):
        """
        Tests if this parser is able to parse the intended user agent, or if it should
        be skipped and another parser should be used instead. Returns either a ``True``
        or ``False`` to indicate whether it can parse the UA or not.

        It is valid for this method to return ``True`` even in cases that it cannot be
        parsed as the system is able to handle false positives, however if it returns
        ``False`` then no further parsing will be attempted by this class.
        """

    @abc.abstractmethod
    def __call__(self, ua):
        """
        Actually parses the user agent, returning a dictionary containing all of the
        relevant parsed information. If this method is unable to parse the user agent
        then it can raise a ``UnableToParse`` exception to indicate that it can't parse
        the given UA.
        """


class CallbackUserAgentParser(UserAgentParser):
    def __init__(self, callback):
        self._callback = callback

    def test(self, ua):
        # Our callback format doesn't give us the ability to determine ahead of time if
        # we can parse the user agent, so we'll just always return True, and the
        # callback will be responsible for handling raising UnableToParse when it can't
        # parse the given user agent.
        return True

    def __call__(self, ua):
        return self._callback(ua)


def ua_parser(fn):
    return CallbackUserAgentParser(fn)
