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

import base64
import binascii
import importlib_resources
import json
import logging
import logging.config

from functools import partial

import asks
import click
import trio

from linehaul.bigquery import BigQuery
from linehaul.migration import migrate as migrate_
from linehaul.server import server as server_


SENSITIVE = {"token"}


asks.init("trio")


logger = logging.getLogger(__name__)


def _configure_bigquery(credentials_file, credentials_blob, api_max_connections=None):
    if credentials_file is None and credentials_blob is None:
        raise click.UsageError(
            "Must pass either --credentials-file or --credentials-blob"
        )
    elif credentials_file is not None and credentials_blob is not None:
        raise click.UsageError(
            "Cannot pass both --credentials-file and --credentials-blob"
        )
    elif credentials_file is not None:
        logger.debug("Configuring BigQuery from %r", credentials_file.name)
        credentials = json.load(credentials_file)
    else:
        logger.debug("Configuring BigQuery from base64 blob")
        credentials = json.loads(credentials_blob)

    return BigQuery(
        credentials["client_email"],
        credentials["private_key"],
        max_connections=api_max_connections,
    )


def _validate_base64(ctx, param, value):
    if value is not None:
        try:
            return base64.b64decode(value)
        except binascii.Error:
            raise click.BadParameter(
                "credentials-blob needs to be a base64 encoded json blob."
            )


@click.group(
    context_settings={
        "auto_envvar_prefix": "LINEHAUL",
        "help_option_names": ["-h", "--help"],
        "max_content_width": 88,
    }
)
@click.option(
    "--log-level",
    type=click.Choice(["spew", "debug", "info", "warning", "error", "critical"]),
    default="info",
    show_default=True,
    help="The verbosity of the console logger.",
)
@click.option(
    "--log-file",
    type=click.Path(file_okay=True, dir_okay=False, writable=True, readable=True),
    help="A file to additionally send logging to.",
)
def cli(log_level, log_file):
    """
    The Linehaul Statistics Daemon.

    Linehaul is a daemon that implements the syslog protocol, listening for specially
    formatted messages corresponding to download events of Python packages. For each
    event it receives it processes them, and then loads them into a BigQuery database.
    """
    handlers = ["console"]
    if log_file:
        handlers.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "class": "logging.Formatter",
                    "style": "{",
                    "format": "[{asctime}] [{levelname:^10}] {message}",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "level": log_level.upper(),
                    "formatter": "console",
                },
                "file": {
                    "class": "logging.handlers.WatchedFileHandler",
                    "filename": log_file or "/dev/null",
                    "level": log_level.upper(),
                    "formatter": "console",
                },
            },
            "root": {"level": "SPEW", "handlers": handlers},
        }
    )


@cli.command(short_help="Runs the Linehaul server.")
@click.option(
    "--credentials-file",
    type=click.File("r", encoding="utf8"),
    help="A path to the credentials JSON for a GCP service account.",
)
@click.option(
    "--credentials-blob",
    callback=_validate_base64,
    help="A base64 encoded JSON blob of credentials for a GCP service account.",
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
@click.option(
    "--tls-certificate",
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True
    ),
    metavar="PATH",
    help="The TLS certificate to serve.",
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
    "--cleanup-timeout",
    type=int,
    default=30,
    metavar="SECONDS",
    show_default=True,
    help="How long to wait for a connection to close gracefully.",
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
    default=10,
    show_default=True,
    help="The maximum number of times to retry sending a batch to BigQuery.",
)
@click.option(
    "--retry-max-wait",
    type=float,
    default=60,
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
    credentials_file,
    credentials_blob,
    bind,
    port,
    tls_certificate,
    token,
    max_line_size,
    recv_size,
    cleanup_timeout,
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
    bq = _configure_bigquery(
        credentials_file, credentials_blob, api_max_connections=api_max_connections
    )

    # Iterate over all of our configuration, and write out the values to the debug
    # logger to make it easier to see if linehaul is picking up a particular
    # configuration or not.
    for key, value in dict(
        bind=bind,
        port=port,
        tls_certificate=tls_certificate,
        token=token,
        max_line_size=max_line_size,
        recv_size=recv_size,
        cleanup_timeout=cleanup_timeout,
        qsize=queued_events,
        batch_size=batch_size,
        batch_timeout=batch_timeout,
        retry_max_attempts=retry_max_attempts,
        retry_max_wait=retry_max_wait,
        retry_multiplier=retry_multiplier,
        api_timeout=api_timeout,
    ).items():
        if key in SENSITIVE:
            value = "*" * 10
        logging.debug("Configuring %s to %r", key, value)

    # Actually run our server via trio.
    try:
        trio.run(
            partial(
                server_,
                bq,
                table,
                bind=bind,
                port=port,
                tls_certificate=tls_certificate,
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
    except KeyboardInterrupt:
        raise
    except BaseException:
        logger.exception("Unhandled error in server.")
        raise


@cli.command()
@click.option(
    "--credentials-file",
    type=click.File("r", encoding="utf8"),
    help="A path to the credentials JSON for a GCP service account.",
)
@click.option(
    "--credentials-blob",
    callback=_validate_base64,
    help="A base64 encoded JSON blob of credentials for a GCP service account.",
)
@click.argument("table")
def migrate(credentials_file, credentials_blob, table):
    """
    Synchronizes the BigQuery table schema.

    TABLE is a BigQuery table identifier of the form ProjectId.DataSetId.TableId.
    """
    bq = _configure_bigquery(credentials_file, credentials_blob)
    schema = json.loads(importlib_resources.read_text("linehaul", "schema.json"))

    trio.run(migrate_, bq, table, schema)
