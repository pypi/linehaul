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

import itertools

from hypothesis import assume, given, strategies as st, reproduce_failure, seed

from .strategies import version as st_version


class TestVersionStrategy:
    @staticmethod
    def _ver_2_list(version):
        version = [int(i) for i in version.split(".")]
        return list(
            reversed(list(itertools.dropwhile(lambda i: i == 0, reversed(version))))
        )

    @given(
        st.data(),
        st.tuples(
            st.integers(min_value=1), st.integers(min_value=1), st.integers(min_value=1)
        ).map(lambda i: ".".join(str(j) for j in i)),
    )
    def test_greater_than_minimum(self, data, min_version):
        version = data.draw(st_version(min_version=min_version))
        assert self._ver_2_list(version) >= self._ver_2_list(min_version)

    @given(
        st.data(),
        st.tuples(
            st.integers(min_value=10),
            st.integers(min_value=1),
            st.integers(min_value=1),
        ).map(lambda i: ".".join(str(j) for j in i)),
    )
    def test_less_than_maximum(self, data, max_version):
        version = data.draw(st_version(max_version=max_version))
        assert self._ver_2_list(version) <= self._ver_2_list(max_version)

    @given(
        st.data(),
        st.tuples(
            st.tuples(
                st.integers(min_value=1),
                st.integers(min_value=1),
                st.integers(min_value=1),
            ),
            st.tuples(
                st.integers(min_value=1),
                st.integers(min_value=1),
                st.integers(min_value=1),
            ),
        ).map(lambda inp: [".".join(str(i) for i in p) for p in sorted(inp)]),
    )
    def test_inbetween_min_and_max(self, data, versions):
        min_version, max_version = versions
        version = data.draw(
            st_version(min_version=min_version, max_version=max_version)
        )
        assert (
            self._ver_2_list(min_version)
            <= self._ver_2_list(version)
            <= self._ver_2_list(max_version)
        )

    @given(st.data(), st.integers(min_value=1, max_value=100))
    def test_produces_with_more_digits_than_min(self, data, min_digits):
        version = data.draw(st_version(min_digits=min_digits))
        assert len(version.split(".")) >= min_digits

    @given(st.data(), st.integers(min_value=2, max_value=100))
    def test_produces_with_less_digits_than_max(self, data, max_digits):
        version = data.draw(st_version(max_digits=max_digits))
        assert len(version.split(".")) <= max_digits

    @given(
        st.data(),
        st.tuples(
            st.integers(min_value=1, max_value=100),
            st.integers(min_value=1, max_value=100),
        ).map(lambda inp: sorted(inp)),
    )
    def test_produces_inbetween_min_and_max_digits(self, data, digits):
        min_digits, max_digits = digits
        version = data.draw(st_version(min_digits=min_digits, max_digits=max_digits))
        assert min_digits <= len(version.split(".")) <= max_digits

    @given(
        st.data(),
        st.tuples(
            st.tuples(
                st.integers(min_value=1),
                st.integers(min_value=1),
                st.integers(min_value=1),
            ),
            st.tuples(
                st.integers(min_value=1),
                st.integers(min_value=1),
                st.integers(min_value=1),
            ),
        ).map(lambda inp: [".".join(str(i) for i in p) for p in sorted(inp)]),
        st.tuples(
            st.integers(min_value=1, max_value=100),
            st.integers(min_value=1, max_value=100),
        ).map(lambda inp: sorted(inp)),
    )
    def test_mixture(self, data, versions, digits):
        min_version, max_version = versions
        min_digits, max_digits = digits

        # Check that the our minimum version doesn't have too many digits.
        # TODO: Can we remove these assumptions?
        assume(len(min_version.split(".")) <= max_digits)
        assume(len(max_version.split(".")) <= max_digits)

        version = data.draw(
            st_version(
                min_digits=min_digits,
                max_digits=max_digits,
                min_version=min_version,
                max_version=max_version,
            )
        )

        assert (
            self._ver_2_list(min_version)
            <= self._ver_2_list(version)
            <= self._ver_2_list(max_version)
        )
        assert min_digits <= len(version.split(".")) <= max_digits
