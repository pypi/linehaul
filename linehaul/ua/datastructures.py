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

from typing import Optional

import attr


@attr.s(slots=True, frozen=True)
class Installer:

    name = attr.ib(type=Optional[str], default=None)
    version = attr.ib(type=Optional[str], default=None)


@attr.s(slots=True, frozen=True)
class Implementation:

    name = attr.ib(type=Optional[str], default=None)
    version = attr.ib(type=Optional[str], default=None)


@attr.s(slots=True, frozen=True)
class LibC:

    lib = attr.ib(type=Optional[str], default=None)
    version = attr.ib(type=Optional[str], default=None)


@attr.s(slots=True, frozen=True)
class Distro:

    name = attr.ib(type=Optional[str], default=None)
    version = attr.ib(type=Optional[str], default=None)
    id = attr.ib(type=Optional[str], default=None)
    libc = attr.ib(type=Optional[LibC], default=None)


@attr.s(slots=True, frozen=True)
class System:

    name = attr.ib(type=Optional[str], default=None)
    release = attr.ib(type=Optional[str], default=None)


@attr.s(slots=True, frozen=True)
class UserAgent:

    installer = attr.ib(type=Optional[Installer], default=None)
    python = attr.ib(type=Optional[str], default=None)
    implementation = attr.ib(type=Optional[Implementation], default=None)
    distro = attr.ib(type=Optional[Distro], default=None)
    system = attr.ib(type=Optional[System], default=None)
    cpu = attr.ib(type=Optional[str], default=None)
    openssl_version = attr.ib(type=Optional[str], default=None)
    setuptools_version = attr.ib(type=Optional[str], default=None)
    ci = attr.ib(type=Optional[bool], default=None)
