#!/usr/bin/env python3.5
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

import asyncio
import ssl

import click
import prometheus_client

from ._click import AsyncCommand
from ._server import Server
from .bigquery import BigQueryClient
from .core import Linehaul


@click.command(cls=AsyncCommand)
@click.option("--bind", default="0.0.0.0")
@click.option("--port", type=int, default=512)
@click.option("--token")
@click.option("--account")
@click.option("--key", type=click.File("r"))
@click.option("--reuse-port/--no-reuse-port", default=True)
@click.option(
    "--tls-ciphers",
    default="ECDHE+CHACHA20:ECDH+AES128GCM:ECDH+AES128:!SHA:!aNULL:!eNULL",
)
@click.option(
    "--tls-certificate",
    type=click.Path(
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
)
@click.option("--metrics-port", type=int, default=12000)
@click.argument("table")
@click.pass_context
async def main(ctx, bind, port, token, account, key, reuse_port, tls_ciphers,
               tls_certificate, metrics_port, table):
    # Start up our metrics server in another thread.
    prometheus_client.start_http_server(metrics_port)

    bqc = BigQueryClient(*table.split(":"), client_id=account, key=key.read())

    if tls_certificate:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ssl_context.load_cert_chain(tls_certificate)
        ssl_context.set_ciphers(tls_ciphers)

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
    else:
        ssl_context = None

    with Linehaul(token=token, bigquery=bqc, loop=ctx.event_loop) as lh:
        async with Server(lh, bind, port,
                          reuse_port=reuse_port,
                          ssl=ssl_context,
                          loop=ctx.event_loop) as s:
            try:
                await s.wait_closed()
            except asyncio.CancelledError:
                click.echo(click.style("Shutting Down...", fg="yellow"))
