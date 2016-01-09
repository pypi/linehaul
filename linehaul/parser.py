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
import ipaddress
import posixpath

import arrow
import pyrsistent

from pyparsing import Combine, Literal as L, QuotedString, Word
from pyparsing import printables, restOfLine, srange
from pyparsing import ParseException


class NullValue:
    pass

NullValue = NullValue()

SP = L(" ").suppress()

NULL = L("(null)")
NULL.setParseAction(lambda s, l, t: NullValue)

TIMESTAMP = QuotedString(quoteChar='"')
TIMESTAMP = TIMESTAMP.setResultsName("timestamp")
TIMESTAMP.setName("Timestamp")

IP_OCTECT = Word(srange("[0-9]"), min=1, max=3)
IP = Combine(IP_OCTECT + "." + IP_OCTECT + "." + IP_OCTECT + "." + IP_OCTECT)
IP = IP.setResultsName("ip")
IP.setName("IP Address")

URL = Word(printables)
URL = URL.setResultsName("url")
URL.setName("URL")

REQUEST = TIMESTAMP + SP + IP + SP + URL

PROJECT_NAME = NULL | Word(srange("[a-zA-Z0-9]") + "._-")
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

PROJECT = PROJECT_NAME + SP + VERSION + SP + PACKAGE_TYPE

USER_AGENT = restOfLine
USER_AGENT = USER_AGENT.setResultsName("user_agent")
USER_AGENT.setName("UserAgent")

MESSAGE = REQUEST + SP + PROJECT + SP + USER_AGENT
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
    project = pyrsistent.field(type=(str, type(None)), mandatory=True)
    version = pyrsistent.field(type=(str, type(None)), mandatory=True)
    package_type = pyrsistent.field(
        type=(str, type(None), PackageType),
        mandatory=True,
        factory=PackageType,
    )


class Download(pyrsistent.PRecord):

    timestamp = pyrsistent.field(
        type=arrow.Arrow,
        mandatory=True,
        factory=lambda t: arrow.get(t[5:-4], "DD MMM YYYY HH:mm:ss"),
    )
    ip = pyrsistent.field(
        type=(ipaddress.IPv4Address, ipaddress.IPv6Address),
        mandatory=True,
        factory=ipaddress.ip_address,
    )
    url = pyrsistent.field(type=str, mandatory=True)
    file = pyrsistent.field(type=File, mandatory=True, factory=File.create)
    user_agent = pyrsistent.field(type=str, mandatory=True)


def _value_or_none(value):
    if value is NullValue:
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
    data["ip"] = parsed.ip
    data["url"] = parsed.url
    data["file"] = {}
    data["file"]["filename"] = posixpath.basename(parsed.url)
    data["file"]["project"] = _value_or_none(parsed.project_name)
    data["file"]["version"] = _value_or_none(parsed.version)
    data["file"]["package_type"] = _value_or_none(parsed.package_type)
    data["user_agent"] = parsed.user_agent

    return Download.create(data)
