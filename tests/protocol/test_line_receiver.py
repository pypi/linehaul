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

from linehaul.protocol.line_receiver import LineReceiver


def test_yields_lines():
    lr = LineReceiver(lambda line: line)
    lines = lr.receive_data(b"This is a line.\nAnd this is another line.\n")
    assert lines == [b"This is a line.\n", b"And this is another line.\n"]
