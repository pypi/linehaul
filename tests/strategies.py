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


INF = float("inf")


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


def _none_for_inf(v):
    if v is INF:
        return None
    return v


@st.composite
def version(draw, min_digits=1, max_digits=None, min_version=None, max_version=None):
    min_version_digits = None if min_version is None else len(min_version.split("."))
    max_version_digits = None if max_version is None else len(max_version.split("."))

    if min_digits < 1:
        raise ValueError("Minimum digits must be >= 1")
    if max_digits is None:
        # To determine our maximum number of digits, we're going to take the larger of
        # our default of 10 greater than the minimum, or the number of digits in the min
        # and max versions.
        max_digits = max(
            filter(None, [min_digits + 10, min_version_digits, max_version_digits])
        )
    if min_digits > max_digits:
        raise ValueError("Maximum digits must be greater than the minimum digits.")
    if min_version_digits is not None and min_version_digits > max_digits:
        raise ValueError(
            "Cannot have a minimum version with more digits than the maximum number "
            "of digits."
        )
    if max_version_digits is not None and max_version_digits > max_digits:
        raise ValueError(
            "Cannot have a maximum version with more digits than the maximum number "
            "of digits."
        )

    num_digits = draw(st.integers(min_value=min_digits, max_value=max_digits))

    if min_version is not None:
        min_version = [int(i) for i in min_version.split(".")]
    else:
        min_version = [0]

    # We need to pad out the minimum version so that it matches our number of digits.
    min_version += [0 for _ in range(num_digits - len(min_version))]

    if max_version is not None:
        # If we were given a max range, than we want to pad it out to zeros to match
        # the number of digits we're trying to generate.
        max_version = [int(i) for i in max_version.split(".")]
        max_version += [0 for _ in range(num_digits - len(max_version))]
    else:
        # If we were not given a max range, we want to have an infinte top end.
        max_version = [INF] * num_digits

    if min_version > max_version:
        raise ValueError("The mininum version *MUST* be less than the maximum version.")

    # The very first version strategy we can have, is simply matching whatever the
    # mininum version is.
    version_strategies = [st.tuples(*[st.just(i) for i in min_version])]

    # Now we have to build up a list of possible versions besides our basic one.
    while min_version:
        # We're going to start with incrementing the rightmost digit in our version.
        incrementing_part = min_version.pop()

        # If the number of digits we would require to handle a version that is
        # larger than this mininum version is greater than the number of digits
        # we're trying to generate in a version, then we'll skip it and move onto
        # the next one.
        # Note: We add one to this to account for the incrementing_part that we removed
        #       from this list earlier.
        if len(min_version) + 1 > num_digits:
            continue

        # We're going to be making a version that has the same prefix as min_version,
        # but the incrementing part is one higher. If doing that would make the version
        # number we're just about to generate greater than our maximum version, then
        # we'll break out of the loop. Any further incrementing will continue to be
        # too large of a version number.
        if min_version + [incrementing_part + 1] > max_version[: len(min_version) + 1]:
            break

        # We're going to limit our generated version by the right most digit in our
        # maximum version.
        max_incrementing_part = max_version[len(min_version)]

        # Build up a parts that is all of the preceding digits, sans the final
        # digit, e.g. if our minimum version is 1.5.6.0, then we want 1, 5, 6.
        # We know this is safe with the maximum version, becasue if it wasn't, then
        # we would have bailed out earlier.
        parts = [st.just(i) for i in min_version]

        # If there are any values where the incrementing part will *always* mean that
        # any version number we generate, no matter what gets generated for the padded
        # versions, then we'll create strategies to deal with those first.
        if min_version + [incrementing_part + 1] < max_version[: len(min_version) + 1]:
            # if incrementing_part + 1 < max_incrementing_part:
            if (
                max_incrementing_part is INF
                or min_version != max_version[: len(min_version)]
            ):
                max_incr_value = None
            else:
                max_incr_value = max_incrementing_part - 1
            subparts = [
                st.integers(min_value=incrementing_part + 1, max_value=max_incr_value)
            ]

            # At this part, we know we can just blindly generate any padding we want,
            # because our leading digits will ensure that we are *always* less than
            # our maximum version.
            # Note: We have to subtract an extra 1 from our number of needed parts to
            #       complete our padding, because of the one we generated above.
            subparts += [
                st.integers(min_value=0) for _ in range(num_digits - len(parts) - 1)
            ]

            # Now we're going to create a hypothesis tuple from our prefix parts, and
            # our subparts, and add it to our list of strategies to try.
            version_strategies.append(st.tuples(*parts + subparts))

        # Finally, we will generate a strategy that sets the incrementing part and all
        # padded parts maximum value to be equal to the maximum value for that part in
        # our maximum value. The only special case here is that Infinity values in our
        # maximum values need to be translated to None for hypothesis. We need one
        # special case here, if our max_incrementing_part is inf, then this case should
        # already have been handled up above.
        if (
            max_incrementing_part is not INF
            and min_version == max_version[: len(min_version)]
        ):
            parts += [st.just(max_incrementing_part)]

            parts += [
                st.integers(min_value=0, max_value=_none_for_inf(max_version[i]))
                for i in range(len(parts), num_digits)
            ]

            # Create a hypothesis tuple from our parts, and add it to our list of
            # strategies to try.
            version_strategies.append(st.tuples(*parts))

    version = draw(st.one_of(version_strategies))

    # Now that we have a list of version strategies, we'll draw from one of those
    # possible strategies, and join the parts together to create a verison number.
    return ".".join(str(i) for i in version)
