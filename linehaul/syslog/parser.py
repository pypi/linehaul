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

import datetime

import arrow
import attr
import attr.validators

from pyparsing import Combine, Literal as L, Word
from pyparsing import srange, restOfLine, printables
from pyparsing import ParseException

from . import Facility, Severity


class UnparseableSyslogMessage(Exception):
    pass


class NilValue:
    pass


NilValue = NilValue()


SP = L(" ").suppress()
LANGLE = L("<").suppress()
RANGLE = L(">").suppress()
LBRACKET = L("[").suppress()
RBRACKET = L("]").suppress()
COLON = L(":").suppress()

NIL = L("-")
NIL.setName("Nil")
NIL.setParseAction(lambda s, l, t: NilValue)

PRIORITY = LANGLE + Word(srange("[0-9]"), min=1, max=3) + RANGLE  # 191 Max
PRIORITY = PRIORITY.setResultsName("priority")
PRIORITY.setName("Priority")
PRIORITY.setParseAction(lambda s, l, t: int(t[0]))

TIMESTAMP = Word(printables)
TIMESTAMP = TIMESTAMP.setResultsName("timestamp")
TIMESTAMP.setName("Timestamp")

HOSTNAME = NIL ^ Word(printables)
HOSTNAME = HOSTNAME.setResultsName("hostname")
HOSTNAME.setName("Hostname")

APPNAME = Word("".join(set(printables) - {"["}))
APPNAME = APPNAME.setResultsName("appname")
APPNAME.setName("AppName")

PROCID = Combine(LBRACKET + Word("".join(set(printables) - {"]"})) + RBRACKET)
PROCID = PROCID.setResultsName("procid")
PROCID.setName("ProcID")

HEADER = PRIORITY + TIMESTAMP + SP + HOSTNAME + SP + APPNAME + PROCID

MESSAGE = restOfLine.setResultsName("message")
MESSAGE.setName("Message")

SYSLOG_MESSAGE = HEADER + COLON + SP + MESSAGE
SYSLOG_MESSAGE.leaveWhitespace()


@attr.s(slots=True, frozen=True)
class SyslogMessage:

    facility = attr.ib(
        type=Facility, converter=Facility, validator=attr.validators.in_(Facility)
    )
    severity = attr.ib(
        type=Severity, converter=Severity, validator=attr.validators.in_(Severity)
    )
    timestamp = attr.ib(
        type=datetime.datetime,
        converter=lambda t: arrow.get(t).naive,
        validator=attr.validators.instance_of(datetime.datetime),
    )
    hostname = attr.ib(
        type=str, validator=attr.validators.instance_of((str, type(None)))
    )
    appname = attr.ib(type=str, validator=attr.validators.instance_of(str))
    procid = attr.ib(type=str, validator=attr.validators.instance_of(str))
    message = attr.ib(type=str, validator=attr.validators.instance_of(str))


def _value_or_none(value):
    if value is NilValue:
        return None
    else:
        return value


def parse(message):
    try:
        parsed = SYSLOG_MESSAGE.parseString(message, parseAll=True)
    except ParseException as exc:
        raise UnparseableSyslogMessage(str(exc)) from None

    data = {}
    data["facility"] = int(parsed.priority / 8)
    data["severity"] = parsed.priority - (data["facility"] * 8)
    data["timestamp"] = parsed.timestamp
    data["hostname"] = _value_or_none(parsed.hostname)
    data["appname"] = parsed.appname
    data["procid"] = parsed.procid
    data["message"] = parsed.message

    return SyslogMessage(**data)
