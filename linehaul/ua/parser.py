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

import json
import logging
import re

import cattr
import packaging.version

from packaging.specifiers import SpecifierSet

from linehaul.ua.datastructures import UserAgent
from linehaul.ua.impl import UnableToParse, ua_parser, regex_ua_parser


logger = logging.getLogger(__name__)


class UnknownUserAgentError(ValueError):
    pass


@ua_parser
def Pip6UserAgent(user_agent):
    # We're only concerned about pip user agents.
    if not user_agent.startswith("pip/"):
        raise UnableToParse

    # This format was brand new in pip 6.0, so we'll need to restrict it
    # to only versions of pip newer than that.
    version_str = user_agent.split()[0].split("/", 1)[1]
    version = packaging.version.parse(version_str)
    if version not in SpecifierSet(">=6", prereleases=True):
        raise UnableToParse

    try:
        return json.loads(user_agent.split(maxsplit=1)[1])
    except json.JSONDecodeError:
        raise UnableToParse from None


@ua_parser
def Pip1_4UserAgent(user_agent):
    # We're only concerned about pip user agents.
    if not user_agent.startswith("pip/"):
        raise UnableToParse

    # This format was brand new in pip 1.4, and went away in pip 6.0, so
    # we'll need to restrict it to only versions of pip between 1.4 and 6.0
    version_str = user_agent.split()[0].split("/", 1)[1]
    version = packaging.version.parse(version_str)
    if version not in SpecifierSet(">=1.4,<6", prereleases=True):
        raise UnableToParse

    _, impl, system = user_agent.split(maxsplit=2)

    data = {
        "installer": {"name": "pip", "version": version_str},
        "implementation": {"name": impl.split("/", 1)[0]},
    }

    if not impl.endswith("/Unknown"):
        data["implementation"]["version"] = impl.split("/", 1)[1]

    if not system.startswith("Unknown/"):
        data.setdefault("system", {})["name"] = system.split("/", 1)[0]

    if not system.endswith("/Unknown"):
        data.setdefault("system", {})["release"] = system.split("/", 1)[1]

    if data["implementation"]["name"].lower() == "cpython" and data[
        "implementation"
    ].get("version"):
        data["python"] = data["implementation"]["version"]

    return data


@regex_ua_parser(r"^Python-urllib/(?P<python>\d\.\d) distribute/(?P<version>\S+)$")
def DistributeUserAgent(*, python, version):
    return {"installer": {"name": "distribute", "version": version}, "python": python}


@regex_ua_parser(
    r"^Python-urllib/(?P<python>\d\.\d) setuptools/(?P<version>\S+)$",
    r"^setuptools/(?P<version>\S+) Python-urllib/(?P<python>\d\.\d)$",
)
def SetuptoolsUserAgent(*, python, version):
    return {"installer": {"name": "setuptools", "version": version}, "python": python}


@regex_ua_parser(r"pex/(?P<version>\S+)$")
def PexUserAgent(*, version):
    return {"installer": {"name": "pex", "version": version}}


@regex_ua_parser(r"^conda/(?P<version>\S+)(?: .+)?$")
def CondaUserAgent(*, version):
    return {"installer": {"name": "conda", "version": version}}


@regex_ua_parser(r"^Bazel/(?P<version>.+)$")
def BazelUserAgent(*, version):
    if version.startswith("release "):
        version = version[8:]

    return {"installer": {"name": "Bazel", "version": version}}


@regex_ua_parser(r"^bandersnatch/(?P<version>\S+) \(.+\)$")
def BandersnatchUserAgent(*, version):
    return {"installer": {"name": "bandersnatch", "version": version}}


@regex_ua_parser(r"devpi-server/(?P<version>\S+) \(.+\)$")
def DevPIUserAgent(*, version):
    return {"installer": {"name": "devpi", "version": version}}


@regex_ua_parser(r"^z3c\.pypimirror/(?P<version>\S+)$")
def Z3CPyPIMirrorUserAgent(*, version):
    return {"installer": {"name": "z3c.pypimirror", "version": version}}


@regex_ua_parser(r"^Artifactory/(?P<version>\S+)$")
def ArtifactoryUserAgent(*, version):
    return {"installer": {"name": "Artifactory", "version": version}}


@regex_ua_parser(r"^Nexus/(?P<version>\S+)")
def NexusUserAgent(*, version):
    return {"installer": {"name": "Nexus", "version": version}}


@regex_ua_parser(r"^pep381client(?:-proxy)?/(?P<version>\S+)$")
def PEP381ClientUserAgent(*, version):
    return {"installer": {"name": "pep381client", "version": version}}


@regex_ua_parser(r"^Python-urllib/(?P<python>\d\.\d)$")
def URLLib2UserAgent(*, python):
    return {"python": python}


@regex_ua_parser(r"^python-requests/(?P<version>\S+)(?: .+)?$")
def RequestsUserAgent(*, version):
    return {"installer": {"name": "requests", "version": version}}


class LegacyParser:
    _os_re = re.compile(
        r"""
        (?:
            ^fetch\ libfetch/\S+$ |
            ^libfetch/\S+$ |
            ^OpenBSD\ ftp$ |
            ^Homebrew\ |
            ^MacPorts/? |
            ^NetBSD-ftp/ |
            ^slapt-get |
            ^pypi-install/ |
            ^slackrepo$ |
            ^PTXdist |
            ^GARstow/ |
            ^xbps/
        )
        """,
        re.VERBOSE,
    )

    @classmethod
    def os_format(cls, user_agent):
        m = cls._os_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "OS"}}

    _homebrew_re = re.compile(
        r"""
        ^
        Homebrew/(?P<version>\S+)
        \s+
        \(Macintosh;\ Intel\ Mac\ OS\ X\ (?P<osx_version>[^)]+)\)
        """,
        re.VERBOSE,
    )

    @classmethod
    def homebrew_format(cls, user_agent):
        m = cls._homebrew_re.search(user_agent)
        if m is None:
            return

        return {
            "installer": {"name": "Homebrew", "version": m.group("version")},
            "distro": {"name": "OS X", "version": m.group("osx_version")},
        }

    _browser_re = re.compile(
        r"""
            ^
            (?:
                Mozilla |
                Safari |
                wget |
                curl |
                Opera |
                aria2 |
                AndroidDownloadManager |
                com\.apple\.WebKit\.Networking/ |
                FDM\ \S+ |
                URL/Emacs |
                Firefox/ |
                UCWEB |
                Links |
                ^okhttp |
                ^Apache-HttpClient
            )
            (?:/|$)
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    @classmethod
    def browser_format(cls, user_agent):
        m = cls._browser_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "Browser"}}

    _ignore_re = re.compile(
        r"""
        (?:
            ^Datadog\ Agent/ |
            ^\(null\)$ |
            ^WordPress/ |
            ^Chef\ (?:Client|Knife)/ |
            ^Ruby$ |
            ^Slackbot-LinkExpanding |
            ^TextualInlineMedia/ |
            ^WeeChat/ |
            ^Download\ Master$ |
            ^Java/ |
            ^Go\ \d\.\d\ package\ http$ |
            ^Go-http-client/ |
            ^GNU\ Guile$ |
            ^github-olee$ |
            ^YisouSpider$ |
            ^Apache\ Ant/ |
            ^Salt/ |
            ^ansible-httpget$ |
            ^ltx71\ -\ \(http://ltx71.com/\) |
            ^Scrapy/ |
            ^spectool/ |
            Nutch |
            ^AWSBrewLinkChecker/ |
            ^Y!J-ASR/ |
            ^NSIS_Inetc\ \(Mozilla\)$ |
            ^Debian\ uscan |
            ^Pingdom\.com_bot_version_\d+\.\d+_\(https?://www.pingdom.com/\)$ |
            ^MauiBot\ \(crawler\.feedback\+dc@gmail\.com\)$
        )
        """,
        re.VERBOSE,
    )

    @classmethod
    def ignored(cls, user_agent):
        m = cls._ignore_re.search(user_agent)
        return m is not None

    @classmethod
    def parse(cls, user_agent):
        formats = [
            cls.requests_format,
            cls.homebrew_format,
            cls.os_format,
            cls.browser_format,
        ]

        for format in formats:
            try:
                data = format(user_agent)
            except Exception as exc:
                logger.warning(
                    "Error parsing %r as %s", user_agent, format.__name__, exc_info=True
                )
                data = None

            if data is not None:
                return cattr.structure(data, UserAgent)

        if cls.ignored(user_agent):
            return

        raise UnknownUserAgentError(user_agent)


# TODO: We should arrange these in order of most common to least common, because the
#       earlier we find a match, the quicker we can finish parsing this user agent.
USER_AGENT_PARSERS = [
    Pip6UserAgent,
    Pip1_4UserAgent,
    DistributeUserAgent,
    SetuptoolsUserAgent,
    PexUserAgent,
    CondaUserAgent,
    BazelUserAgent,
    BandersnatchUserAgent,
    DevPIUserAgent,
    Z3CPyPIMirrorUserAgent,
    ArtifactoryUserAgent,
    NexusUserAgent,
    PEP381ClientUserAgent,
    URLLib2UserAgent,
    RequestsUserAgent,
]


def parse(user_agent, *, _parsers=USER_AGENT_PARSERS):
    for parser in _parsers:
        if parser.test(user_agent):
            try:
                parsed = parser(user_agent)
            except UnableToParse:
                pass
            except Exception:
                logger.error(
                    "Error parsing %r as a %s", user_agent, parser.name, exc_info=True
                )
            else:
                return cattr.structure(parsed, UserAgent)

    # This handles user agents that we haven't ported over to the new mechanism for
    # parsing yet.
    # TODO: Port over all formats to the new system, and then raise
    #       UnknownUserAgentError here instead of calling Parser.parse().
    return LegacyParser.parse(user_agent)
