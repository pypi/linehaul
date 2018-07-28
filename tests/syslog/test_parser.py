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

import pyparsing

from hypothesis import example, given, strategies as st

from linehaul.syslog import Facility, Severity
from linehaul.syslog.parser import SyslogMessage, parse


def _unparse_syslog_message(sm):
    pri = (sm.facility.value * 8) + sm.severity.value
    timestamp = sm.timestamp.isoformat()
    hostname = "-" if sm.hostname is None else sm.hostname
    return f"<{pri}>{timestamp}Z {hostname} {sm.appname}[{sm.procid}]: {sm.message}"


@given(
    st.builds(
        SyslogMessage,
        timestamp=st.datetimes(),
        hostname=(
            st.none()
            | st.text(alphabet=pyparsing.printables, min_size=1, max_size=100).filter(
                lambda i: i != "-"
            )
        ),
        appname=st.text(
            alphabet=list(set(pyparsing.printables) - set("[]")),
            min_size=1,
            max_size=100,
        ),
        procid=st.text(
            alphabet=list(set(pyparsing.printables) - set("[]")),
            min_size=1,
            max_size=100,
        ),
        message=st.text(min_size=1, max_size=250).filter(
            lambda i: not (set(i) & set("\n\t"))
        ),
    )
)
@example(
    SyslogMessage(
        facility=Facility.kernel,
        severity=Severity.emergency,
        timestamp=datetime.datetime(2000, 1, 1, 0, 0),
        hostname="-0",
        appname="0",
        procid="0",
        message="0",
    )
)
def test_syslog_parsing(syslog_message):
    line = _unparse_syslog_message(syslog_message)
    assert parse(line) == syslog_message
