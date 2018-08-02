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

import json
import os.path

import cattr
import pytest
import yaml

from hypothesis import given, strategies as st

from linehaul.ua import parser
from linehaul.ua.datastructures import UserAgent

from ...strategies import version as st_version


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_ua_fixtures(fixture_dir):
    fixtures = os.listdir(fixture_dir)
    for filename in fixtures:
        with open(os.path.join(fixture_dir, filename), "r") as fp:
            fixtures = yaml.safe_load(fp.read())
        for fixture in fixtures:
            ua = fixture.pop("ua")
            result = fixture.pop("result")
            expected = (
                cattr.structure(result, UserAgent)
                if isinstance(result, dict)
                else result
            )
            assert fixture == {}
            yield ua, expected


@pytest.mark.parametrize(("ua", "expected"), _load_ua_fixtures(FIXTURE_DIR))
def test_user_agent_parsing(ua, expected):
    assert parser.parse(ua) == expected


def _is_valid_json(item):
    try:
        json.loads(item)
    except Exception:
        return False

    return True


class TestPip6UserAgent:
    @given(st.text().filter(lambda i: not i.startswith("pip/")))
    def test_not_pip(self, ua):
        with pytest.raises(parser.UnableToParse):
            parser.Pip6UserAgent(ua)

    @given(st_version(max_version="6"))
    def test_invalid_version(self, version):
        with pytest.raises(parser.UnableToParse):
            parser.Pip6UserAgent(f"pip/{version}")

    @given(st.text(max_size=100).filter(lambda i: not _is_valid_json(i)))
    def test_invalid_json(self, json_blob):
        with pytest.raises(parser.UnableToParse):
            parser.Pip6UserAgent(f"pip/18.0 {json_blob}")


class TestPip1_4UserAgent:
    @given(st.text().filter(lambda i: not i.startswith("pip/")))
    def test_not_pip(self, ua):
        with pytest.raises(parser.UnableToParse):
            parser.Pip1_4UserAgent(ua)

    @given(st_version(max_version="1.3") | st_version(min_version="6"))
    def test_invalid_version(self, version):
        with pytest.raises(parser.UnableToParse):
            parser.Pip1_4UserAgent(f"pip/{version} Unknown/Unknown Unknown/Unknown")

    @given(st_version(min_version="1.4", max_version="5"))
    def test_no_other_data(self, version):
        with pytest.raises(parser.UnableToParse):
            parser.Pip1_4UserAgent(f"pip/{version}")

    @given(
        st_version(min_version="1.4", max_version="5"),
        (
            st.just("Unknown")
            | st.just("Cpython")
            | st.just("PyPy")
            | st.text(
                min_size=1,
                alphabet=st.characters(
                    blacklist_categories=["Cc", "Z"], blacklist_characters="/"
                ),
            )
        ),
        (
            st.just("Unknown")
            | st_version()
            | st.text(
                min_size=1,
                alphabet=st.characters(
                    blacklist_categories=["Cc", "Z"], blacklist_characters="/"
                ),
            )
        ),
        (
            st.just("Unknown")
            | st.just("Darwin")
            | st.just("Linux")
            | st.just("Windows")
            | st.text(
                min_size=1,
                alphabet=st.characters(
                    blacklist_categories=["Cc", "Z"], blacklist_characters="/"
                ),
            )
        ),
        (
            st.just("Unknown")
            | st.just("17.7.0")
            | st.just("NT")
            | st_version()
            | st.text(
                min_size=1,
                alphabet=st.characters(
                    blacklist_categories=["Cc", "Z"], blacklist_characters="/"
                ),
            )
        ),
    )
    def test_valid_data(
        self, version, impl_name, impl_version, system_name, system_release
    ):
        ua = f"pip/{version} {impl_name}/{impl_version} {system_name}/{system_release}"

        expected = {"installer": {"name": "pip", "version": version}}
        if impl_name.lower() != "unknown":
            expected.setdefault("implementation", {})["name"] = impl_name
        if impl_version.lower() != "unknown":
            expected.setdefault("implementation", {})["version"] = impl_version
        if system_name.lower() != "unknown":
            expected.setdefault("system", {})["name"] = system_name
        if system_release.lower() != "unknown":
            expected.setdefault("system", {})["release"] = system_release
        if impl_name.lower() == "cpython":
            expected["python"] = impl_version

        assert parser.Pip1_4UserAgent(ua) == expected


class TestParse:
    @given(st.text())
    def test_unknown_user_agent(self, user_agent):
        with pytest.raises(parser.UnknownUserAgentError):
            parser.parse(user_agent)
