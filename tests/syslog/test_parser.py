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

from linehaul.syslog import Facility, Severity
from linehaul.syslog.parser import SyslogMessage, parse


def test_basic():
    msg = parse("<134>2018-07-20T02:19:20Z cache-itm18828 linehaul[411617]: A Message!")

    assert msg == SyslogMessage(
        facility=Facility.local0,
        severity=Severity.informational,
        timestamp=datetime.datetime(
            year=2018, month=7, day=20, hour=2, minute=19, second=20
        ),
        hostname="cache-itm18828",
        appname="linehaul",
        procid="411617",
        message="A Message!",
    )
