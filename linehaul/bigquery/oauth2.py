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

import time

import jwt

from oauthlib.common import to_unicode
from oauthlib.oauth2.rfc6749.clients.base import Client
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from oauthlib.oauth2.rfc6749.parameters import prepare_token_request


__all__ = ["ServiceApplicationClient", "TokenExpiredError"]


class ServiceApplicationClient(Client):

    grant_type = "urn:ietf:params:oauth:grant-type:jwt-bearer"

    def __init__(
        self,
        client_id,
        private_key=None,
        subject=None,
        issuer=None,
        audience=None,
        **kwargs
    ):
        super().__init__(client_id, **kwargs)

        self.private_key = private_key
        self.subject = subject
        self.issuer = issuer
        self.audience = audience

    def prepare_request_body(
        self,
        private_key=None,
        subject=None,
        issuer=None,
        audience=None,
        expires_at=None,
        issued_at=None,
        extra_claims=None,
        body="",
        scope=None,
        **kwargs
    ):
        key = private_key or self.private_key
        if not key:
            raise ValueError(
                "Encryption key must be supplied to make JWT token requests."
            )

        claim = {
            "iss": issuer or self.issuer,
            "aud": audience or self.audience,
            "sub": subject,
            "exp": int(expires_at or time.time() + 3600),
            "iat": int(issued_at or time.time()),
            "scope": scope,
        }

        for attr in {"iss", "aud"}:
            if claim[attr] is None:
                raise ValueError(
                    "Claim must include {} but none was given.".format(attr)
                )

        if "not_before" in kwargs:
            claim["nbf"] = kwargs.pop("not_before")

        if "jwt_id" in kwargs:
            claim["jti"] = kwargs.pop("jwt_id")

        claim.update(extra_claims or {})

        assertion = jwt.encode(claim, key, "RS256")
        assertion = to_unicode(assertion)

        return prepare_token_request(
            self.grant_type, body=body, assertion=assertion, **kwargs
        )
