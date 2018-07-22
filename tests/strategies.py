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

from hypothesis import strategies as st


@st.composite
def line_delimited_data(draw, max_line_size, min_lines=1):
    n = draw(max_line_size)
    data = st.binary(min_size=1, max_size=n).filter(lambda d: b"\n" not in d)
    lines = draw(
        st.lists(data, min_size=min_lines).filter(
            lambda l: sum(map(len, l)) + len(l) <= n
        )
    )
    return b"\n".join(lines) + b"\n"


@st.composite
def chunked(draw, source):
    data = draw(source)

    chunk_sizes = [0]
    chunk_sizes += draw(
        st.lists(st.integers(0, len(data) - 1), unique=True).map(sorted)
    )
    chunk_sizes += [len(data)]

    return [data[u:v] for u, v in zip(chunk_sizes, chunk_sizes[1:])]
