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
from linehaul.ua.impl import ParserSet, UnableToParse, ua_parser, regex_ua_parser


logger = logging.getLogger(__name__)


class UnknownUserAgentError(ValueError):
    pass


# Note: This is a ParserSet, not a ParserList, parsers that have been registered with
#       it may be called in any order. That means that all of our parsers need to be
#       ordering independent.
_parser = ParserSet()


@_parser.register
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
    except (json.JSONDecodeError, UnicodeDecodeError, IndexError):
        raise UnableToParse from None


@_parser.register
@regex_ua_parser(
    (
        r"^pip/(?P<version>\S+) (?P<impl_name>\S+)/(?P<impl_version>\S+) "
        r"(?P<system_name>\S+)/(?P<system_release>\S+)$"
    )
)
def Pip1_4UserAgent(*, version, impl_name, impl_version, system_name, system_release):
    # This format was brand new in pip 1.4, and went away in pip 6.0, so
    # we'll need to restrict it to only versions of pip between 1.4 and 6.0.
    if version not in SpecifierSet(">=1.4,<6", prereleases=True):
        raise UnableToParse

    data = {"installer": {"name": "pip", "version": version}}

    if impl_name.lower() != "unknown":
        data.setdefault("implementation", {})["name"] = impl_name

    if impl_version.lower() != "unknown":
        data.setdefault("implementation", {})["version"] = impl_version

    if system_name.lower() != "unknown":
        data.setdefault("system", {})["name"] = system_name

    if system_release.lower() != "unknown":
        data.setdefault("system", {})["release"] = system_release

    if impl_name.lower() == "cpython":
        data["python"] = impl_version

    return data


@_parser.register
@regex_ua_parser(r"^Python-urllib/(?P<python>\d\.\d) distribute/(?P<version>\S+)$")
def DistributeUserAgent(*, python, version):
    return {"installer": {"name": "distribute", "version": version}, "python": python}


@_parser.register
@regex_ua_parser(
    r"^Python-urllib/(?P<python>\d\.\d) setuptools/(?P<version>\S+)$",
    r"^setuptools/(?P<version>\S+) Python-urllib/(?P<python>\d\.\d)$",
)
def SetuptoolsUserAgent(*, python, version):
    return {"installer": {"name": "setuptools", "version": version}, "python": python}


@_parser.register
@regex_ua_parser(r"pex/(?P<version>\S+)$")
def PexUserAgent(*, version):
    return {"installer": {"name": "pex", "version": version}}


@_parser.register
@regex_ua_parser(r"^conda/(?P<version>\S+)(?: .+)?$")
def CondaUserAgent(*, version):
    return {"installer": {"name": "conda", "version": version}}


@_parser.register
@regex_ua_parser(r"^Bazel/(?:release\s+)?(?P<version>.+)$")
def BazelUserAgent(*, version):
    return {"installer": {"name": "Bazel", "version": version}}


@_parser.register
@regex_ua_parser(r"^bandersnatch/(?P<version>\S+) \(.+\)$")
def BandersnatchUserAgent(*, version):
    return {"installer": {"name": "bandersnatch", "version": version}}


@_parser.register
@regex_ua_parser(r"devpi-server/(?P<version>\S+) \(.+\)$")
def DevPIUserAgent(*, version):
    return {"installer": {"name": "devpi", "version": version}}


@_parser.register
@regex_ua_parser(r"^z3c\.pypimirror/(?P<version>\S+)$")
def Z3CPyPIMirrorUserAgent(*, version):
    return {"installer": {"name": "z3c.pypimirror", "version": version}}


@_parser.register
@regex_ua_parser(r"^Artifactory/(?P<version>\S+)$")
def ArtifactoryUserAgent(*, version):
    return {"installer": {"name": "Artifactory", "version": version}}


@_parser.register
@regex_ua_parser(r"^Nexus/(?P<version>\S+)")
def NexusUserAgent(*, version):
    return {"installer": {"name": "Nexus", "version": version}}


@_parser.register
@regex_ua_parser(r"^pep381client(?:-proxy)?/(?P<version>\S+)$")
def PEP381ClientUserAgent(*, version):
    return {"installer": {"name": "pep381client", "version": version}}


# TODO: We should probably consider not parsing this specially, and moving it to
#       just the same as we treat browsers, since we don't really know anything
#       about it-- including whether or not the version of Python mentioned is
#       the one they're going to install it into or not. The one real sticking
#       point is that before pip 1.4, pip just used the default urllib2 UA, so
#       right now we're counting pip 1.4 in here... but pip 1.4 usage is probably
#       low enough not to worry about that any more.
@_parser.register
@regex_ua_parser(r"^Python-urllib/(?P<python>\d\.\d)$")
def URLLib2UserAgent(*, python):
    return {"python": python}


# TODO: We should probably consider not parsing this specially, and moving it to
#       just the same as we treat browsers, since we don't really know anything
#       about it and the version of requests isn't very useful in general.
@_parser.register
@regex_ua_parser(r"^python-requests/(?P<version>\S+)(?: .+)?$")
def RequestsUserAgent(*, version):
    return {"installer": {"name": "requests", "version": version}}


@_parser.register
@regex_ua_parser(
    (
        r"^Homebrew/(?P<version>\S+) "
        r"\(Macintosh; Intel (?:Mac OS X|macOS) (?P<osx_version>[^)]+)\)(?: .+)?$"
    )
)
def HomebrewUserAgent(*, version, osx_version):
    return {
        "installer": {"name": "Homebrew", "version": version},
        "distro": {"name": "OS X", "version": osx_version},
    }


# TODO: It would be nice to maybe break more of these apart to try and get more insight
#       into the OSs that people are installing packages into (similiar to Homebrew).
@_parser.register
@regex_ua_parser(
    re.compile(
        r"""
    (?:
        ^fetch\ libfetch/\S+$ |
        ^libfetch/\S+$ |
        ^OpenBSD\ ftp$ |
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
)
def OSUserAgent():
    return {"installer": {"name": "OS"}}


@_parser.register
@regex_ua_parser(
    re.compile(
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
)
def BrowserUserAgent():
    return {"installer": {"name": "Browser"}}


# TODO: It would be kind of nice to implement this as just another parser, that returns
#       None instead of a dictionary. However given that there is no inherent ordering
#       in a ParserSet, and we want this to always go last (just incase an ignore
#       pattern is overlly broad) we can't do that. It would be nice to make it possible
#       to register a parser with an explicit location in the parser set.
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


def parse(user_agent):
    try:
        return cattr.structure(_parser(user_agent), UserAgent)
    except UnableToParse:
        # If we were not able to parse the user agent, then we have two options, we can
        # either raise an `UnknownUserAgentError` or we can return None to explicitly
        # say that we opted not to parse this user agent. To determine which option we
        # pick we'll match against a regex of UAs to ignore, if we match then we'll
        # return a None to indicate to our caller that we couldn't parse this UA, but
        # that it was an expected inability to parse. Otherwise we'll raise an
        # `UnknownUserAgentError` to indicate that it as an unexpected inability to
        # parse.
        if _ignore_re.search(user_agent) is not None:
            return None

        raise UnknownUserAgentError from None
