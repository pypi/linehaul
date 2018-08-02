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
import collections
import logging
import random
import re


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
        self._parsers = []

        self._optimize_every = 1000000
        # Set the first optimize in to a reduced amount to get some basic optimization
        # done early.
        self._optimize_in = self._optimize_every * 0.25
        self._counts = collections.Counter()

    def register(self, parser, *, _randomize=True):
        self._parsers.append(parser)

        # The use of random.shuffle here is a bit quirkly, it doesn't actually help us
        # at runtime in any way. What it *does* do, is make it more likely that any
        # ordering dependence in registered parsers shows up as test failures instead
        # of being hard to find bugs in production.
        # This does make registering a parser more heavy-weight than recorded (through
        # minorly so), but this shouldn't matter since in our usage registerin is only
        # done at the module level anyways.
        if _randomize:
            random.shuffle(self._parsers)

        return parser

    def _optimize(self):
        # We're going to sort our list in place, using the value of how many times
        # a parser function has been used as the parser for a user agent to put the
        # most commonly used parsed first.
        self._parsers.sort(key=lambda p: self._counts[p], reverse=True)

        # Reduce our recorded counts just to keep the size of our counts in checks.
        # This will also implicitly act as a decay so that historical data is less
        # relevant than new data.
        self._counts.subtract({k: int(v * 0.5) for k, v in self._counts.items()})

        # Reset our marker
        self._optimize_in = self._optimize_every

    def __call__(self, user_agent):
        # Decrement our counter for how long until we will implicitly call optimize
        # on our ParserSet, and check to see if it's time to optimize or not.
        self._optimize_in -= 1
        if self._optimize_in <= 0:
            self._optimize()

        # Actually go through our registered parsers and try to use them to parse.
        for parser in self._parsers:
            try:
                parsed = parser(user_agent)

                # Record a "hit" for this parser.
                self._counts[parser] += 1

                return parsed
            except UnableToParse:
                pass
            except Exception:
                logger.error(
                    "Error parsing %r as a %s.", user_agent, parser.name, exc_info=True
                )

        raise UnableToParse
