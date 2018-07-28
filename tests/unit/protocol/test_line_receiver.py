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

from functools import partial

import pytest

from hypothesis import given, strategies as st

from linehaul.protocol.line_receiver import (
    LineReceiver,
    BufferTooLargeError,
    TruncatedLineError,
)

from ...strategies import line_delimited_data as _line_delimited_data, chunked


_max_line_size = st.integers(min_value=1, max_value=32768)
max_line_size = st.shared(_max_line_size, key="max-line-size")

line_delimited_data = partial(
    _line_delimited_data, max_line_size=st.shared(_max_line_size, key="max-line-size")
)


@given(max_line_size, chunked(line_delimited_data()))
def test_yields_lines(max_line_size, data):
    lr = LineReceiver(lambda line: line, max_line_size=max_line_size)

    lines = []
    for chunk in data:
        lines.extend(lr.receive_data(chunk))
    lr.close()

    assert lines == [i + b"\n" for i in b"".join(data).split(b"\n")[:-1]]


@given(max_line_size | st.none(), st.integers(min_value=1, max_value=20))
def test_too_large_line_raises(max_line_size, over_by):
    lr = LineReceiver(lambda line: line, max_line_size=max_line_size)

    with pytest.raises(BufferTooLargeError):
        lr.receive_data(bytes(lr._max_line_size + over_by))


@given(st.binary(min_size=1, max_size=512).filter(lambda i: i[-1:] != b"\n"))
def test_truncated_line_raises(truncated_data):
    lr = LineReceiver(lambda line: line)
    lr.receive_data(truncated_data)

    with pytest.raises(TruncatedLineError):
        lr.close()


_lines_of_line_delimited_data = line_delimited_data(
    max_line_size=st.just(512), min_lines=2
).map(lambda d: d.split(b"\n")[:-1])
lines_of_line_delimited_data = st.shared(
    _lines_of_line_delimited_data, key="lines-of-line-delimited-data"
).map(lambda lst: b"\n".join(lst) + b"\n")


@given(
    chunked(lines_of_line_delimited_data),
    st.shared(
        _lines_of_line_delimited_data, key="lines-of-line-delimited-data"
    ).flatmap(lambda lst: st.sampled_from(lst)),
)
def test_skips_none_return_callback(data, skipped):
    skipped = skipped + b"\n"
    lr = LineReceiver(lambda line: None if line == skipped else line)

    lines = []
    for chunk in data:
        lines.extend(lr.receive_data(chunk))
    lr.close()

    assert lines == [
        i + b"\n" for i in b"".join(data).split(b"\n")[:-1] if i != skipped[:-1]
    ]
