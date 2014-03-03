# Copyright 2013 Donald Stufft
#
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
from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import argparse

import alchimia
import yaml
import sqlalchemy

from twisted.internet.defer import Deferred
from twisted.internet.endpoints import StandardIOEndpoint
from twisted.internet.task import react

from linehaul.core import FastlySyslogProtocolFactory
from linehaul.migrations import cli as migrate


def _process_logs(reactor, config):
    finished = Deferred()

    download_statistic_engine = sqlalchemy.create_engine(
        config["database"],
        strategy=alchimia.TWISTED_STRATEGY,
        reactor=reactor
    )
    endpoint = StandardIOEndpoint(reactor)
    endpoint.listen(
        FastlySyslogProtocolFactory(download_statistic_engine, finished),
    )
    return finished


def main():
    parser = argparse.ArgumentParser(prog="linehaul")
    parser.add_argument(
        "--config", "-c",
        dest="_config",
        metavar="CONFIG",
        help="Location of the Config File",
    )

    subparsers = parser.add_subparsers()

    # Create the process command
    parser_process = subparsers.add_parser("process")
    parser_process.set_defaults(
        _func=lambda config: react(_process_logs, [config]),
    )

    # Create the db command
    parser_db = subparsers.add_parser("db")
    db_subparsers = parser_db.add_subparsers()

    # Create db upgrade
    db_upgrade = db_subparsers.add_parser("upgrade")
    db_upgrade.set_defaults(_func=migrate.upgrade)
    db_upgrade.add_argument("revision", help="revision identifier")

    # Create db branches
    db_branches = db_subparsers.add_parser("branches")
    db_branches.set_defaults(_func=migrate.branches)

    # Create db stamp
    db_stamp = db_subparsers.add_parser("stamp")
    db_stamp.set_defaults(_func=migrate.stamp)
    db_stamp.add_argument("revision", help="revision identifier")

    # Create db current
    db_current = db_subparsers.add_parser("current")
    db_current.set_defaults(_func=migrate.current)
    db_current.add_argument(
        "--head-only",
        action="store_true",
        dest="head_only",
        help=("Only show current version and whether or not this is the "
              "head revision."),
    )

    # Create db downgrade
    db_downgrade = db_subparsers.add_parser("downgrade")
    db_downgrade.set_defaults(_func=migrate.downgrade)
    db_downgrade.add_argument("revision", help="revision identifier")

    # Create db history
    db_history = db_subparsers.add_parser("history")
    db_history.set_defaults(_func=migrate.history)
    db_history.add_argument(
        "-r", "--rev-range",
        dest="rev_range",
        help="Specify a revision range; format is [start]:[end]",
    )

    # Create db revision
    db_revision = db_subparsers.add_parser("revision")
    db_revision.set_defaults(_func=migrate.revision)
    db_revision.add_argument(
        "-m", "--message",
        dest="message",
        help="Message string to use with 'revision'",
    )
    db_revision.add_argument(
        "-a", "--autogenerate",
        action="store_true",
        dest="autogenerate",
        help=("Populate revision script with candidate migration "
              "operations, based on comparison of database to model."),
    )

    # Parse our args
    args = parser.parse_args()

    # Construct our Config
    if args._config is not None:
        with open(args._config, "r") as fp:
            config = yaml.safe_load(fp.read())
    else:
        config = {}

    return args._func(
        config,
        *args._get_args(),
        **{k: v for k, v in args._get_kwargs() if not k.startswith("_")}
    )
