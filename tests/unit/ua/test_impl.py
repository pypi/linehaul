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
