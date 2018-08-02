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

import itertools
import logging
import re

import pytest

from linehaul.ua import impl


class TestDecorators:
    def test_ua_parser(self, monkeypatch):
        class FakeCallbackParser:
            def __init__(self, *args, **kwargs):
                self.args = list(args)
                self.kwargs = kwargs

        monkeypatch.setattr(impl, "CallbackUserAgentParser", FakeCallbackParser)

        def MyParserFn():
            pass

        MyParser = impl.ua_parser(MyParserFn)

        assert isinstance(MyParser, FakeCallbackParser)
        assert MyParser.args == [MyParserFn]
        assert MyParser.kwargs == {}

    @pytest.mark.parametrize("regexes", [(r"^one$",), (r"^one$", r"^two$")])
    def test_regex_us_parser(self, monkeypatch, regexes):
        class FakeRegexParser:
            def __init__(self, *args, **kwargs):
                self.args = list(args)
                self.kwargs = kwargs

        monkeypatch.setattr(impl, "RegexUserAgentParser", FakeRegexParser)

        def MyHandlerFn():
            pass

        MyParser = impl.regex_ua_parser(*regexes)(MyHandlerFn)

        assert isinstance(MyParser, FakeRegexParser)
        assert MyParser.args == [regexes, MyHandlerFn]
        assert MyParser.kwargs == {}


class TestCallbackUserAgentParser:
    def test_undefined_name(self):
        def FakeUserAgent():
            pass

        parser = impl.CallbackUserAgentParser(FakeUserAgent)
        assert parser.name == "FakeUserAgent"

    def test_explicit_name(self):
        parser = impl.CallbackUserAgentParser(lambda i: i, name="MyName")
        assert parser.name == "MyName"

    def test_returns_on_success(self):
        result = object()
        parser = impl.CallbackUserAgentParser(lambda inp: result)
        assert parser("any input") is result

    def test_passed_input(self):
        parser = impl.CallbackUserAgentParser(lambda inp: {"input": inp})
        assert parser("another input") == {"input": "another input"}


class TestRegexUserAgentParser:
    def test_undefined_name(self):
        def FakeUserAgent():
            pass

        parser = impl.RegexUserAgentParser([], FakeUserAgent)
        assert parser.name == "FakeUserAgent"

    def test_explicit_name(self):
        parser = impl.RegexUserAgentParser([], lambda i: i, name="MyName")
        assert parser.name == "MyName"

    @pytest.mark.parametrize(
        ("regexes", "input"),
        [
            ([r"^Foo Bar$"], "Foo Bar"),
            ([re.compile(r"^Foo Bar$")], "Foo Bar"),
            ([r"^Bar Foo$", re.compile(r"^Foo Bar$")], "Foo Bar"),
            ([r"^Bar Foo$", re.compile(r"^Foo Bar$")], "Bar Foo"),
        ],
    )
    def test_valid(self, regexes, input):
        result = object()
        parser = impl.RegexUserAgentParser(regexes, lambda: result)
        assert parser(input) is result

    @pytest.mark.parametrize(
        ("regexes", "input"),
        [
            ([], "literally anything"),
            ([r"^A Test String$"], "totally not a test string"),
            ([r"^One$", re.compile(r"^Two$")], "Three"),
        ],
    )
    def test_invalid(self, regexes, input):
        parser = impl.RegexUserAgentParser(regexes, None, name="AName")
        with pytest.raises(impl.UnableToParse):
            parser(input)

    def test_positional_captures(self):
        def handler(*args):
            return list(args)

        parser = impl.RegexUserAgentParser([r"^Foo (.+)$"], handler)
        assert parser("Foo Bar") == ["Bar"]

    def test_named_captures(self):
        def handler(**kwargs):
            return kwargs

        parser = impl.RegexUserAgentParser([r"^Foo (?P<thing>.+)$"], handler)
        assert parser("Foo Bar") == {"thing": "Bar"}

    def test_mixed_captures(self):
        def handler(*args, **kwargs):
            return list(args), kwargs

        parser = impl.RegexUserAgentParser(
            [r"^(\S+) (?P<thing>\S+) (\S+) (?P<another>\S+)$"], handler
        )
        assert parser("Foo Bar Widget Frob") == (
            ["Foo", "Widget"],
            {"thing": "Bar", "another": "Frob"},
        )


class TestParserSet:
    def test_valid(self):
        def raiser(inp):
            raise impl.UnableToParse

        parser = impl.ParserSet()

        parser.register(raiser)
        parser.register(lambda i: {"parsed": "data"})
        parser.register(raiser)

        assert parser("anything") == {"parsed": "data"}

    def test_cannot_parse(self):
        def raiser(inp):
            raise impl.UnableToParse

        parser = impl.ParserSet()
        parser.register(raiser)

        with pytest.raises(impl.UnableToParse):
            parser("anything")

    def test_error_while_parsing(self, caplog):
        def raiser(inp):
            raise ValueError("Oh No")

        raiser.name = "OhNoName"

        parser = impl.ParserSet()
        parser.register(raiser)

        with pytest.raises(impl.UnableToParse):
            parser("anything")

        assert caplog.record_tuples == [
            (
                "linehaul.ua.impl",
                logging.ERROR,
                "Error parsing 'anything' as a OhNoName.",
            )
        ]

    def test_optimizing(self):
        parser = impl.ParserSet()

        # Override some values to make it easier to test.
        parser._optimize_every = 100
        parser._optimize_in = 100

        def parser1(inp):
            if inp != "one":
                raise impl.UnableToParse

        def parser2(inp):
            if inp != "two" and inp != "three":
                raise impl.UnableToParse

        def parser3(inp):
            if inp != "four":
                raise impl.UnableToParse

        # We explicitly register these with the private, randomize kwarg set to
        # False, that will ensure that our default order is the ordered we registered
        # these in, which will make this test easier to write.
        parser.register(parser1, _randomize=False)
        parser.register(parser2, _randomize=False)
        parser.register(parser3, _randomize=False)

        # Check our start state makes sense.
        assert parser._parsers == [parser1, parser2, parser3]

        # Run through our parser with some input, watching the state of our optimize
        # markers as we go along.
        for i, value in enumerate(itertools.cycle(["one", "two", "three", "four"])):
            assert parser._optimize_in == parser._optimize_every - i
            parser(value)
            assert parser._optimize_in == parser._optimize_every - i - 1
            assert parser._parsers == [parser1, parser2, parser3]

            # Break out of our loop right before the optimize method would be called.
            if i + 1 >= 99:
                break

        # We should know the exact state of our counters at this point.
        assert parser._counts == {parser1: 25, parser2: 50, parser3: 24}

        # Call our parser one more time, we explictly call it with "one" here, because
        # that should ensure that the first parser has been called at least once more
        # than the third person, and the second parser should have been called almost
        # twice as many times as either.
        parser("one")

        assert parser._optimize_in == 100
        assert parser._parsers == [parser2, parser1, parser3]
        assert parser._counts == {parser1: 14, parser2: 25, parser3: 12}
