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

from hypothesis import given, strategies as st

from linehaul.protocol.line_receiver import LineReceiver

from ..strategies import line_delimited_data as _line_delimited_data, chunked


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
