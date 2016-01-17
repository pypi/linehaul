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

import os.path
import ssl

from linehaul import _tls as tls


def test_creates_context():
    ctx = tls.create_context(
        os.path.join(os.path.dirname(__file__), "test.pem"),
        "ECDHE+CHACHA20:ECDH+AES128GCM:ECDH+AES128:!SHA:!aNULL:!eNULL",
    )

    assert ctx.protocol == ssl.PROTOCOL_SSLv23

    assert (ctx.options & ssl.OP_NO_SSLv2) == ssl.OP_NO_SSLv2
    assert (ctx.options & ssl.OP_NO_SSLv3) == ssl.OP_NO_SSLv3
    assert (ctx.options & ssl.OP_NO_TLSv1) == ssl.OP_NO_TLSv1
    assert (ctx.options & ssl.OP_NO_TLSv1_1) == ssl.OP_NO_TLSv1_1

    assert (ctx.options & ssl.OP_CIPHER_SERVER_PREFERENCE) == \
        ssl.OP_CIPHER_SERVER_PREFERENCE
    assert (ctx.options & ssl.OP_SINGLE_DH_USE) == ssl.OP_SINGLE_DH_USE
    assert (ctx.options & ssl.OP_SINGLE_ECDH_USE) == ssl.OP_SINGLE_ECDH_USE
    assert (ctx.options & ssl.OP_NO_COMPRESSION) == ssl.OP_NO_COMPRESSION
