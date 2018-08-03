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

import inspect
import os
import os.path

import pytest
import yaml

from hypothesis import given, strategies as st

from linehaul.events.parser import Download, UnparseableEvent, parse, _cattr


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_event_fixtures(fixture_dir):
    fixtures = os.listdir(fixture_dir)
    for filename in fixtures:
        with open(os.path.join(fixture_dir, filename), "r") as fp:
            fixtures = yaml.load(fp.read())
        for fixture in fixtures:
            event = fixture.pop("event")
            result = fixture.pop("result")
            expected = (
                _cattr.structure(result, Download)
                if isinstance(result, dict)
                else result
            )
            assert fixture == {}
            yield event, expected


@pytest.mark.parametrize(("event_data", "expected"), _load_event_fixtures(FIXTURE_DIR))
def test_download_parsing(event_data, expected):
    if inspect.isclass(expected) and issubclass(expected, Exception):
        with pytest.raises(expected):
            parse(event_data)
    else:
        assert parse(event_data) == expected


@given(st.text(alphabet=st.characters(blacklist_characters=["\n"])))
def test_invalid_event(data):
    with pytest.raises(UnparseableEvent):
        parse(data)
