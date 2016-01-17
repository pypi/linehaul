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

import ssl


def create_context(certificate, ciphers):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_context.load_cert_chain(certificate)
    ssl_context.set_ciphers(ciphers)

    # Even though our SSLContext allows SSLv2+ and TLSv1+ we want to
    # restrict it to just TLSv1.2+.
    ssl_context.options |= ssl.OP_NO_SSLv2
    ssl_context.options |= ssl.OP_NO_SSLv3
    ssl_context.options |= ssl.OP_NO_TLSv1
    ssl_context.options |= ssl.OP_NO_TLSv1_1

    # Set a few options to get a better level of security.
    ssl_context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE
    ssl_context.options |= ssl.OP_SINGLE_DH_USE
    ssl_context.options |= ssl.OP_SINGLE_ECDH_USE
    ssl_context.options |= ssl.OP_NO_COMPRESSION

    return ssl_context
