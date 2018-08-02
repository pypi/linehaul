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

import os.path

import cattr
import pytest
import yaml

from linehaul.ua.datastructures import UserAgent
from linehaul.ua.parser import parse


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_ua_fixtures(fixture_dir):
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


@pytest.mark.parametrize(("ua", "expected"), load_ua_fixtures(FIXTURE_DIR))
def test_user_agent_parsing(ua, expected):
    assert parse(ua) == expected
