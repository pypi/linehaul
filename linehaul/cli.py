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

import importlib_resources
import json

from functools import partial

import asks
import click
import trio

from linehaul.bigquery import BigQuery
from linehaul.migration import migrate as migrate_
from linehaul.server import server as server_


asks.init("trio")


@click.group(
    context_settings={
        "auto_envvar_prefix": "LINEHAUL",
        "help_option_names": ["-h", "--help"],
        "max_content_width": 88,
    }
)
def cli():
    """
    The Linehaul Statistics Daemon.

    Linehaul is a daemon that implements the syslog protocol, listening for specially
    formatted messages corresponding to download events of Python packages. For each
    event it receives it processes them, and then loads them into a BigQuery database.
    """


@cli.command(short_help="Runs the Linehaul server.")
@click.option(
    "--credentials",
    type=click.File("r", encoding="utf8"),
    required=True,
    help="A path to the credentials JSON for a GCP service account.",
)
@click.option(
    "--bind",
    default="0.0.0.0",
    metavar="ADDR",
    show_default=True,
    help="The IP address to bind to.",
)
@click.option(
    "--port",
    type=int,
    default=512,
    metavar="PORT",
    show_default=True,
    help="The port to bind to.",
)
@click.option("--token", help="A token used to authenticate a remote syslog stream.")
@click.option(
    "--max-line-size",
    type=int,
    default=16384,
    metavar="BYTES",
    show_default=True,
    help="The maximum length in bytes of a single incoming syslog event.",
)
@click.option(
    "--recv-size",
    type=int,
    default=8192,
    metavar="BYTES",
    show_default=True,
    help="How many bytes to read per recv.",
)
@click.option(
    "--queued-events",
    type=int,
    default=10000,
    show_default=True,
    help="How many events to queue for processing before applying backpressure.",
)
@click.option(
    "--batch-size",
    type=int,
    default=500,
    show_default=True,
    help="The number of events to send in each BigQuery API call.",
)
@click.option(
    "--batch-timeout",
    type=int,
    default=30,
    metavar="SECONDS",
    show_default=True,
    help=(
        "How long to wait before sending a smaller than --batch-size batch of events "
        "to BigQuery."
    ),
)
@click.option(
    "--retry-max-attempts",
    type=int,
    default=15,
    show_default=True,
    help="The maximum number of times to retry sending a batch to BigQuery.",
)
@click.option(
    "--retry-max-wait",
    type=float,
    default=300,
    metavar="SECONDS",
    show_default=True,
    help=(
        "The maximum length of time to wait between retrying sending a batch to "
        "BigQuery."
    ),
)
@click.option(
    "--retry-multiplier",
    type=float,
    default=0.5,
    metavar="SECONDS",
    show_default=True,
    help=(
        "The multiplier for exponential back off between retrying sending a batch to "
        "BigQuery."
    ),
)
@click.option(
    "--api-timeout",
    type=int,
    default=30,
    metavar="SECONDS",
    show_default=True,
    help="How long to wait for a single API call to BigQuery to complete.",
)
@click.option(
    "--api-max-connections",
    type=int,
    default=30,
    show_default=True,
    help="Maximum number of concurrent connections to BigQuery.",
)
@click.argument("table")
def server(
    credentials,
    bind,
    port,
    token,
    max_line_size,
    recv_size,
    queued_events,
    batch_size,
    batch_timeout,
    retry_max_attempts,
    retry_max_wait,
    retry_multiplier,
    api_timeout,
    api_max_connections,
    table,
):
    """
    Starts a server in the foreground that listens for incoming syslog events, processes
    them, and then inserts them into the BigQuery table at TABLE.

    TABLE is a BigQuery table identifier of the form ProjectId.DataSetId.TableId.
    """
    credentials = json.load(credentials)
    bq = BigQuery(
        credentials["client_email"],
        credentials["private_key"],
        max_connections=api_max_connections,
    )

    trio.run(
        partial(
            server_,
            bq,
            table,
            bind=bind,
            port=port,
            token=token,
            max_line_size=max_line_size,
            recv_size=recv_size,
            qsize=queued_events,
            batch_size=batch_size,
            batch_timeout=batch_timeout,
            retry_max_attempts=retry_max_attempts,
            retry_max_wait=retry_max_wait,
            retry_multiplier=retry_multiplier,
            api_timeout=api_timeout,
        ),
        restrict_keyboard_interrupt_to_checkpoints=True,
    )


@cli.command()
@click.option(
    "--credentials",
    type=click.File("r", encoding="utf8"),
    required=True,
    help="A path to the credentials JSON for a GCP service account.",
)
@click.argument("table")
def migrate(credentials, table):
    """
    Synchronizes the BigQuery table schema.

    TABLE is a BigQuery table identifier of the form ProjectId.DataSetId.TableId.
    """
    credentials = json.load(credentials)
    bq = BigQuery(credentials["client_email"], credentials["private_key"])
    schema = json.loads(importlib_resources.read_text("linehaul", "schema.json"))

    trio.run(migrate_, bq, table, schema)
