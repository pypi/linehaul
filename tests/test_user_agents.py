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

import pytest

from linehaul import user_agents as ua


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        (
            'pip/7.1.2 {"cpu":"x86_64","distro":{"name":"OS X","version":"'
            '10.11.2"},"implementation":{"name":"CPython","version":"3.5.1"},'
            '"installer":{"name":"pip","version":"7.1.2"},"python":"3.5.1",'
            '"system":{"name":"Darwin","release":"15.2.0"}}',
            {
                "cpu": "x86_64",
                "distro": {"version": "10.11.2", "name": "OS X"},
                "implementation": {"version": "3.5.1", "name": "CPython"},
                "installer": {"version": "7.1.2", "name": "pip"},
                "python": "3.5.1",
                "system": {"release": "15.2.0", "name": "Darwin"},
            },
        ),
        (
            "pip/1.5.6 CPython/3.5.1 Darwin/15.2.0",
            {
                "installer": {"name": "pip", "version": "1.5.6"},
                "implementation": {"name": "CPython", "version": "3.5.1"},
                "python": "3.5.1",
                "system": {"name": "Darwin", "release": "15.2.0"},
            },
        ),
        (
            "pip/1.5.6 CPython/Unknown Darwin/15.2.0",
            {
                "installer": {"name": "pip", "version": "1.5.6"},
                "implementation": {"name": "CPython"},
                "system": {"name": "Darwin", "release": "15.2.0"},
            },
        ),
        (
            "pip/1.5.6 CPython/3.5.1 Unknown/15.2.0",
            {
                "installer": {"name": "pip", "version": "1.5.6"},
                "implementation": {"name": "CPython", "version": "3.5.1"},
                "python": "3.5.1",
                "system": {"release": "15.2.0"},
            },
        ),
        (
            "pip/1.5.6 CPython/3.5.1 Darwin/Unknown",
            {
                "installer": {"name": "pip", "version": "1.5.6"},
                "implementation": {"name": "CPython", "version": "3.5.1"},
                "python": "3.5.1",
                "system": {"name": "Darwin"},
            },
        ),
        (
            "pip/1.5.6 CPython/3.5.1 Unknown/Unknown",
            {
                "installer": {"name": "pip", "version": "1.5.6"},
                "implementation": {"name": "CPython", "version": "3.5.1"},
                "python": "3.5.1",
            },
        ),
        ("Python-urllib/3.5", {"python": "3.5"}),
        (
            "Python-urllib/3.5 distribute/0.6.12",
            {
                "installer": {"name": "distribute", "version": "0.6.12"},
                "python": "3.5",
            },
        ),
        (
            "Python-urllib/3.5 setuptools/18.0",
            {
                "installer": {"name": "setuptools", "version": "18.0"},
                "python": "3.5",
            },
        ),
        ("pex/1.0", {"installer": {"name": "pex", "version": "1.0"}}),
        ("conda/1.0", {"installer": {"name": "conda", "version": "1.0"}}),
        (
            "bandersnatch/1.8 (CPython 2.7.11-final0, Darwin 15.2.0 x86_64)",
            {"installer": {"name": "bandersnatch", "version": "1.8"}},
        ),
        (
            "devpi-server/1.0 (py3.5.1; darwin)",
            {"installer": {"name": "devpi", "version": "1.0"}},
        ),
        (
            "z3c.pypimirror/1.0",
            {"installer": {"name": "z3c.pypimirror", "version": "1.0"}},
        ),
        (
            "Artifactory/1.0",
            {"installer": {"name": "Artifactory", "version": "1.0"}},
        ),
        (
            "pep381client/1.0",
            {"installer": {"name": "pep381client", "version": "1.0"}},
        ),
        (
            "python-requests/2.9.1",
            {"installer": {"name": "requests", "version": "2.9.1"}},
        ),
        ("OpenBSD ftp", {"installer": {"name": "OS"}}),
        ("fetch libfetch/2.0", {"installer": {"name": "OS"}}),
        ("libfetch/2.0", {"installer": {"name": "OS"}}),
        ("wget/1.0", {"installer": {"name": "Browser"}}),
    ],
)
def test_valid_user_agent(user_agent, expected):
    assert ua.parse(user_agent) == ua.UserAgent.create(expected)


@pytest.mark.parametrize(
    "user_agent",
    [
        "Debian uscan/1.0",
    ],
)
def test_ignored_user_agent(user_agent):
    assert ua.parse(user_agent) is None


@pytest.mark.parametrize(
    "user_agent",
    [
        "something that is not a known user agent",
        "pip/1.0 there-never-was-a-pip-1.0-user-agent",
        "Python-urllib/3.5 unknownthing/1.0",
    ],
)
def test_invalid_user_agent(user_agent):
    with pytest.raises(ValueError):
        ua.parse(user_agent)
