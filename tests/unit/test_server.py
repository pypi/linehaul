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
import logging

from unittest.mock import ANY

import arrow

from hypothesis import given, strategies as st

from linehaul.events.parser import Download
from linehaul.server import compute_batches, extract_item_date, parse_line


class TestParseLine:
    @given(
        st.shared(
            st.text(min_size=1).map(lambda tkn: tkn.encode("utf8")),
            key="parse-line-token",
        ),
        (
            st.shared(
                st.text(min_size=1).map(lambda tkn: tkn.encode("utf8")),
                key="parse-line-token",
            ).flatmap(
                lambda tkn: st.binary().filter(
                    lambda ln: b"\n" not in ln and not ln.startswith(tkn)
                )
            )
        ),
    )
    def test_invalid_token_skips(self, token, line):
        assert parse_line(line, token=token) is None

    @given(
        st.none() | st.text(min_size=1).map(lambda tkn: tkn.encode("utf8")),
        st.binary().filter(lambda ln: b"\n" not in ln),
    )
    def test_unparseable_syslog(self, caplog, token, line):
        if token is not None:
            line = token + line

        caplog.clear()

        assert parse_line(line, token=token) is None
        assert caplog.record_tuples == [("linehaul.server", logging.ERROR, ANY)]
        assert caplog.record_tuples[0][2].startswith("Unparseable syslog message")

    @given(
        st.none() | st.text(min_size=1).map(lambda tkn: tkn.encode("utf8")),
        st.binary()
        .filter(lambda ln: b"\n" not in ln)
        .map(
            lambda d: b"<134>2018-07-20T02:19:20Z cache-itm18828 linehaul[411617]: " + d
        ),
    )
    def test_unparseable_event(self, caplog, token, line):
        if token is not None:
            line = token + line

        caplog.clear()

        assert parse_line(line, token=token) is None
        assert caplog.record_tuples == [("linehaul.server", logging.ERROR, ANY)]
        assert caplog.record_tuples[0][2].startswith("Unparseable event:")


@given(
    st.builds(
        Download,
        timestamp=st.shared(st.dates(), key="extract-item-data").map(
            lambda i: arrow.Arrow.fromdate(i)
        ),
    ),
    st.shared(st.dates(), key="extract-item-data").map(
        lambda i: f"{i.year:04}{i.month:02}{i.day:02}"
    ),
)
def test_extract_item_data(download, expected):
    assert extract_item_date(download) == expected


@given(
    st.lists(
        st.builds(Download, timestamp=st.dates().map(lambda i: arrow.Arrow.fromdate(i)))
    )
)
def test_compute_batches(events):
    total_events = 0

    ids = set()
    for template_suffix, batch in compute_batches(events):
        # Count all of our events, so that we can verify we didn't get any extra or
        # missing events.
        total_events += len(batch)

        template_date = datetime.datetime.strptime(template_suffix, "%Y%m%d").date()
        for item in batch:
            # Make sure that all of the items in this batch, are of the correct date
            assert (
                datetime.date.fromtimestamp(item["json"]["timestamp"]) == template_date
            )

            # Make sure we've generated a unique identifier for each row.
            ids.add(item["insertId"])

    assert len(ids) == len(events)
    assert total_events == len(events)
