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
import logging
import posixpath

from typing import Optional

import arrow
import attr
import attr.validators
import cattr

from packaging.utils import canonicalize_name
from pyparsing import Literal as L, Word, Optional as OptionalItem
from pyparsing import printables as _printables, restOfLine
from pyparsing import ParseException

from linehaul.ua import UserAgent, parser as user_agents


logger = logging.getLogger(__name__)


_cattr = cattr.Converter()
_cattr.register_structure_hook(
    arrow.Arrow, lambda d, t: arrow.get(d[5:-4], "DD MMM YYYY HH:mm:ss")
)


class UnparseableEvent(Exception):
    pass


class NullValue:
    pass


NullValue = NullValue()


printables = "".join(set(_printables + " " + "\t") - {"|", "@"})

PIPE = L("|").suppress()

AT = L("@").suppress()

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

REQUEST = TIMESTAMP + PIPE + OptionalItem(COUNTRY_CODE) + PIPE + URL

PROJECT_NAME = NULL | Word(printables)
PROJECT_NAME = PROJECT_NAME.setResultsName("project_name")
PROJECT_NAME.setName("Project Name")

VERSION = NULL | Word(printables)
VERSION = VERSION.setResultsName("version")
VERSION.setName("Version")

PACKAGE_TYPE = NULL | (
    L("sdist")
    | L("bdist_wheel")
    | L("bdist_dmg")
    | L("bdist_dumb")
    | L("bdist_egg")
    | L("bdist_msi")
    | L("bdist_rpm")
    | L("bdist_wininst")
)
PACKAGE_TYPE = PACKAGE_TYPE.setResultsName("package_type")
PACKAGE_TYPE.setName("Package Type")

PROJECT = PROJECT_NAME + PIPE + VERSION + PIPE + PACKAGE_TYPE

TLS_PROTOCOL = NULL | Word(printables)
TLS_PROTOCOL = TLS_PROTOCOL.setResultsName("tls_protocol")
TLS_PROTOCOL.setName("TLS Protocol")

TLS_CIPHER = NULL | Word(printables)
TLS_CIPHER = TLS_CIPHER.setResultsName("tls_cipher")
TLS_CIPHER.setName("TLS Cipher")

TLS = TLS_PROTOCOL + PIPE + TLS_CIPHER

USER_AGENT = restOfLine
USER_AGENT = USER_AGENT.setResultsName("user_agent")
USER_AGENT.setName("UserAgent")

SIMPLE_SIGIL = L("simple")
SIMPLE_SIGIL = SIMPLE_SIGIL.setResultsName("message_type")
SIMPLE_SIGIL.setName("Message Type")

SIMPLE_MESSAGE = SIMPLE_SIGIL + PIPE + REQUEST + PIPE + TLS + PIPE + USER_AGENT

DOWNLOAD_SIGIL = L("download")
DOWNLOAD_SIGIL = DOWNLOAD_SIGIL.setResultsName("message_type")
DOWNLOAD_SIGIL.setName("message_type")

DOWNLOAD_MESSAGE = (
    DOWNLOAD_SIGIL + PIPE + REQUEST + PIPE + TLS + PIPE + PROJECT + PIPE + USER_AGENT
)

V1_HEADER = OptionalItem(L("1").suppress() + AT)

MESSAGE_v1 = V1_HEADER + REQUEST + PIPE + PROJECT + PIPE + USER_AGENT
MESSAGE_v1.leaveWhitespace()

V2_HEADER = L("2").suppress() + AT

MESSAGE_v2 = V2_HEADER + REQUEST + PIPE + TLS + PIPE + PROJECT + PIPE + USER_AGENT
MESSAGE_v2.leaveWhitespace()

V3_HEADER = L("3").suppress() + AT

MESSAGE_v3 = V3_HEADER + (SIMPLE_MESSAGE | DOWNLOAD_MESSAGE)

MESSAGE = MESSAGE_v3 | MESSAGE_v2 | MESSAGE_v1


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


@attr.s(slots=True, frozen=True)
class File:

    filename = attr.ib(validator=attr.validators.instance_of(str))
    project = attr.ib(validator=attr.validators.instance_of(str))
    version = attr.ib(validator=attr.validators.instance_of(str))
    type = attr.ib(type=PackageType)


@attr.s(slots=True, frozen=True)
class Download:

    timestamp = attr.ib(type=arrow.Arrow)
    url = attr.ib(validator=attr.validators.instance_of(str))
    file = attr.ib(type=File)
    tls_protocol = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    tls_cipher = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    country_code = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    details = attr.ib(type=Optional[UserAgent], default=None)


@attr.s(slots=True, frozen=True)
class SimpleRequest:
    timestamp = attr.ib(type=arrow.Arrow)
    url = attr.ib(validator=attr.validators.instance_of(str))
    project = attr.ib(validator=attr.validators.instance_of(str))
    tls_protocol = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    tls_cipher = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    country_code = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    details = attr.ib(type=Optional[UserAgent], default=None)


def _value_or_none(value):
    if value is NullValue or value == "":
        return None
    else:
        return value


def _parse_download(parsed):
    data = {}
    data["timestamp"] = parsed.timestamp
    data["tls_protocol"] = _value_or_none(parsed.tls_protocol)
    data["tls_cipher"] = _value_or_none(parsed.tls_cipher)
    data["country_code"] = _value_or_none(parsed.country_code)
    data["url"] = parsed.url
    data["file"] = {}
    data["file"]["filename"] = posixpath.basename(parsed.url)
    data["file"]["project"] = _value_or_none(parsed.project_name)
    data["file"]["version"] = _value_or_none(parsed.version)
    data["file"]["type"] = _value_or_none(parsed.package_type)

    return _cattr.structure(data, Download)


def _parse_simple(parsed):
    data = {}
    data["timestamp"] = parsed.timestamp
    data["tls_protocol"] = _value_or_none(parsed.tls_protocol)
    data["tls_cipher"] = _value_or_none(parsed.tls_cipher)
    data["country_code"] = _value_or_none(parsed.country_code)
    data["url"] = parsed.url
    data["project"] = canonicalize_name(posixpath.split(parsed.url.rstrip("/"))[-1])

    return _cattr.structure(data, SimpleRequest)


_DISPATCH = {"download": _parse_download, "simple": _parse_simple}


def parse(message):
    try:
        parsed = MESSAGE.parseString(message, parseAll=True)
    except ParseException as exc:
        raise UnparseableEvent("{!r} {}".format(message, exc)) from None

    event = _DISPATCH[parsed.message_type](parsed)

    try:
        ua = user_agents.parse(parsed.user_agent)
        if ua is None:
            return  # Ignored user agents mean we'll skip trying to log this event
    except user_agents.UnknownUserAgentError:
        logging.info("Unknown User agent: %r", parsed.user_agent)
    else:
        event = attr.evolve(event, details=ua)

    return event
