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


class LegacyParser:
    _z3c_pypimirror_re = re.compile(r"^z3c\.pypimirror/(?P<version>\S+)$")

    @classmethod
    def z3c_pypimirror_format(cls, user_agent):
        m = cls._z3c_pypimirror_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "z3c.pypimirror", "version": m.group("version")}}

    _artifactory_re = re.compile(r"^Artifactory/(?P<version>\S+)$")

    @classmethod
    def artifactory_format(cls, user_agent):
        m = cls._artifactory_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "Artifactory", "version": m.group("version")}}

    _nexus_re = re.compile(r"^Nexus/(?P<version>\S+)")

    @classmethod
    def nexus_format(cls, user_agent):
        m = cls._nexus_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "Nexus", "version": m.group("version")}}

    _pep381client_re = re.compile(r"^pep381client(?:-proxy)?/(?P<version>\S+)$")

    @classmethod
    def pep381client_format(cls, user_agent):
        m = cls._pep381client_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "pep381client", "version": m.group("version")}}

    @staticmethod
    def urllib2_format(user_agent):
        # This isn't really a format exactly, prior to pip 1.4 pip used urllib2
        # and it didn't bother to change the default user agent. This means
        # we'll miscount this version as higher than it actually is, however
        # I'm not sure there is any better way around that.
        if not user_agent.startswith("Python-urllib/"):
            return

        # Some projects (like setuptools) add an additional item to the end of
        # the urllib string. We want to make sure this is _only_ Python-urllib
        if len(user_agent.split()) > 1:
            return

        return {"python": user_agent.split("/", 1)[1]}

    _requests_re = re.compile(r"^python-requests/(?P<version>\S+)(?: .+)?$")

    @classmethod
    def requests_format(cls, user_agent):
        # Older versions of devpi used requests without modifying the user
        # agent. However this could also just be someone using requests to
        # download things from PyPI naturally. This means we can't count this
        # as anything other than requests, but it might be something else.
        m = cls._requests_re.search(user_agent)
        if m is None:
            return

        return {"installer": {"name": "requests", "version": m.group("version")}}

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
            cls.z3c_pypimirror_format,
            cls.artifactory_format,
            cls.nexus_format,
            cls.pep381client_format,
            cls.urllib2_format,
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
