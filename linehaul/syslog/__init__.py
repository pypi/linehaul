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


@enum.unique
class Facility(enum.IntEnum):
    kernel = 0
    user = 1
    mail = 2
    daemon = 3
    auth = 4
    syslog = 5
    lpr = 6
    news = 7
    uucp = 8
    clock = 9
    authpriv = 10
    ftp = 11
    ntp = 12
    audit = 13
    alert = 14
    cron = 15
    local0 = 16
    local1 = 17
    local2 = 18
    local3 = 19
    local4 = 20
    local5 = 21
    local6 = 22
    local7 = 23


@enum.unique
class Severity(enum.IntEnum):
    emergency = 0
    alert = 1
    critical = 2
    error = 3
    warning = 4
    notice = 5
    informational = 6
    debug = 7
