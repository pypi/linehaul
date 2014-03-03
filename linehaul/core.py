# Copyright 2013 Donald Stufft
#
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
from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import json
import logging

from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineOnlyReceiver

from linehaul.helpers import parse_log_line
from linehaul.models import DownloadStatisticsModels


logger = logging.getLogger(__name__)


class FastlySyslogProtocol(LineOnlyReceiver):
    delimiter = b"\n"

    def __init__(self, models, finished):
        self._models = models
        self._finished = finished

    def connectionLost(self, reason):
        self._finished.callback(None)

    def lineReceived(self, line):
        try:
            self.handle_line(line)
        except Exception:
            logger.exception(json.dumps({
                "event": "download_statistics.lineReceived.exception",
                "line": repr(line)
            }))

    def handle_line(self, line):
        parsed = parse_log_line(line)
        if parsed is None:
            return

        ua = parsed.user_agent
        self._models.create_download(
            package_name=parsed.package_name,
            package_version=parsed.package_version,
            distribution_type=parsed.distribution_type,
            python_type=ua.python_type,
            python_release=ua.python_release,
            python_version=ua.python_version,
            installer_type=ua.installer_type,
            installer_version=ua.installer_version,
            operating_system=ua.operating_system,
            operating_system_version=ua.operating_system_version,
            download_time=parsed.download_time,
            raw_user_agent=ua.raw_user_agent,
        )


class FastlySyslogProtocolFactory(Factory):
    def __init__(self, engine, finished):
        self._engine = engine
        self._finished = finished

    def buildProtocol(self, addr):
        return FastlySyslogProtocol(
            DownloadStatisticsModels(self._engine),
            self._finished,
        )
