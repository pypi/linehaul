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
import re


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


class RegexUserAgentParser(UserAgentParser):
    def __init__(self, regexes, handler):
        self._regexes = [
            re.compile(regex) if isinstance(regex, str) else regex for regex in regexes
        ]
        self._handler = handler

    def test(self, user_agent):
        return any(regex.search(user_agent) is not None for regex in self._regexes)

    def __call__(self, user_agent):
        for regex in self._regexes:
            matched = regex.search(user_agent)

            # If we've matched this particuar regex, then we'll break the loop here and
            # go onto finishing parsing.
            if matched is not None:
                break
        else:
            # We shouldn't actually be able to ever get here unless the caller did not
            # test this parser before attempting to use it. However, we'll guard against
            # it anyways just to be safe.
            raise UnableToParse

        # We need to build up the args, and kwargs of our function, we call any unnamed
        # group an arg, and pass them in, in order, and we call any named group a kwarg
        # and we pass them in by name.
        group_to_name = {v: k for k, v in matched.re.groupindex.items()}
        args, kwargs = [], {}
        for i, value in enumerate(matched.groups(), start=1):
            name = group_to_name.get(i)
            if name is not None:
                kwargs[name] = value
            else:
                args.append(value)

        # Finally, we'll call our handler with our parsed arguments, and return whatever
        # result it gives us.
        return self._handler(*args, **kwargs)


def regex_ua_parser(*regexes):
    def deco(fn):
        return RegexUserAgentParser(regexes, fn)

    return deco
