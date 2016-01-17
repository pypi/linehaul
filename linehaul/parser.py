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

import enum
import posixpath

import arrow
import pyrsistent

from pyparsing import Literal as L, Word, Optional
from pyparsing import printables as _printables, restOfLine
from pyparsing import ParseException

from . import user_agents


class NullValue:
    pass

NullValue = NullValue()


printables = "".join(set(_printables + " " + "\t") - {"|"})

PIPE = L("|").suppress()

NULL = L("(null)")
NULL.setParseAction(lambda s, l, t: NullValue)

TIMESTAMP = Word(printables)
TIMESTAMP = TIMESTAMP.setResultsName("timestamp")
TIMESTAMP.setName("Timestamp")

COUNTRY_CODE = Word(printables)
COUNTRY_CODE = COUNTRY_CODE.setResultsName("country_code")
COUNTRY_CODE.setName("Country Code")

URL = Word(printables)
URL = URL.setResultsName("url")
URL.setName("URL")

REQUEST = TIMESTAMP + PIPE + Optional(COUNTRY_CODE) + PIPE + URL

PROJECT_NAME = NULL | Word(printables)
PROJECT_NAME = PROJECT_NAME.setResultsName("project_name")
PROJECT_NAME.setName("Project Name")

VERSION = NULL | Word(printables)
VERSION = VERSION.setResultsName("version")
VERSION.setName("Version")

PACKAGE_TYPE = NULL | (
    L("sdist") | L("bdist_wheel") | L("bdist_dmg") | L("bdist_dumb") |
    L("bdist_egg") | L("bdist_msi") | L("bdist_rpm") | L("bdist_wininst")
)
PACKAGE_TYPE = PACKAGE_TYPE.setResultsName("package_type")
PACKAGE_TYPE.setName("Package Type")

PROJECT = PROJECT_NAME + PIPE + VERSION + PIPE + PACKAGE_TYPE

USER_AGENT = restOfLine
USER_AGENT = USER_AGENT.setResultsName("user_agent")
USER_AGENT.setName("UserAgent")

MESSAGE = REQUEST + PIPE + PROJECT + PIPE + USER_AGENT
MESSAGE.leaveWhitespace()


@enum.unique
class PackageType(enum.Enum):
    bdist_dmg = "bdist_dmg"
    bdist_dumb = "bdist_dumb"
    bdist_egg = "bdist_egg"
    bdist_msi = "bdist_msi"
    bdist_rpm = "bdist_rpm"
    bdist_wheel = "bdist_wheel"
    bdist_wininst = "bdist_wininst"
    sdist = "sdist"
    unknown = None


class File(pyrsistent.PRecord):

    filename = pyrsistent.field(type=str, mandatory=True)
    project = pyrsistent.field(type=str, mandatory=True)
    version = pyrsistent.field(type=str, mandatory=True)
    type = pyrsistent.field(
        type=(str, PackageType),
        mandatory=True,
        factory=PackageType,
        serializer=lambda format, d: d.value,
    )


class Download(pyrsistent.PRecord):

    timestamp = pyrsistent.field(
        type=arrow.Arrow,
        mandatory=True,
        factory=lambda t: arrow.get(t[5:-4], "DD MMM YYYY HH:mm:ss"),
    )
    country_code = pyrsistent.field(type=(str, type(None)), mandatory=True)
    url = pyrsistent.field(type=str, mandatory=True)
    file = pyrsistent.field(type=File, mandatory=True, factory=File.create)
    details = pyrsistent.field(type=user_agents.UserAgent)


def _value_or_none(value):
    if value is NullValue or value == "":
        return None
    else:
        return value


def parse(message):
    try:
        parsed = MESSAGE.parseString(message, parseAll=True)
    except ParseException as exc:
        raise ValueError("{!r} {}".format(message, exc)) from None

    data = {}
    data["timestamp"] = parsed.timestamp
    data["country_code"] = _value_or_none(parsed.country_code)
    data["url"] = parsed.url
    data["file"] = {}
    data["file"]["filename"] = posixpath.basename(parsed.url)
    data["file"]["project"] = _value_or_none(parsed.project_name)
    data["file"]["version"] = _value_or_none(parsed.version)
    data["file"]["type"] = _value_or_none(parsed.package_type)

    ua = user_agents.parse(parsed.user_agent)
    if ua is None:
        return  # Ignored user agents mean we'll skip trying to log this event

    data["details"] = ua

    try:
        return Download.create(data)
    except (pyrsistent.PTypeError, pyrsistent.InvariantException) as exc:
        raise ValueError(str(exc)) from None
