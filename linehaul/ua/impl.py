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
import logging
import re

import cattr

from linehaul.ua.datastructures import UserAgent


logger = logging.getLogger(__name__)


class UnableToParse(Exception):
    pass


class UserAgentParser(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def name(self):
        """
        Returns the name of this parser, useful for things like logging etc.
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
    def __init__(self, callback, *, name=None):
        if name is None:
            name = callback.__name__

        self._callback = callback
        self._name = name

    @property
    def name(self):
        return self._name

    def __call__(self, ua):
        return self._callback(ua)


def ua_parser(fn):
    return CallbackUserAgentParser(fn)


class RegexUserAgentParser(UserAgentParser):
    def __init__(self, regexes, handler, *, name=None):
        if name is None:
            name = handler.__name__

        self._regexes = [
            re.compile(regex) if isinstance(regex, str) else regex for regex in regexes
        ]
        self._handler = handler
        self._name = name

    @property
    def name(self):
        return self._name

    def __call__(self, user_agent):
        for regex in self._regexes:
            matched = regex.search(user_agent)

            # If we've matched this particuar regex, then we'll break the loop here and
            # go onto finishing parsing.
            if matched is not None:
                break
        else:
            # None of our regexes matched.
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


class ParserSet:
    def __init__(self):
        self._parsers = set()

    def register(self, parser):
        self._parsers.add(parser)
        return parser

    def __call__(self, user_agent):
        for parser in self._parsers:
            try:
                parsed = parser(user_agent)
            except UnableToParse:
                pass
            except Exception:
                logger.error(
                    "Error parsing %r as a %s", user_agent, parser.name, exc_info=True
                )
            else:
                return cattr.structure(parsed, UserAgent)

        raise UnableToParse
