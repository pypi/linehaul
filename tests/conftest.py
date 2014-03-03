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
from __future__ import absolute_import, division, print_function
from __future__ import unicode_literals

import os
import random
import string

import alembic.config
import alembic.command
import pytest
import sqlalchemy
import sqlalchemy.pool


def pytest_addoption(parser):
    group = parser.getgroup("linehaul")
    group._addoption(
        "--database-url",
        default=None,
        help="The url to connect when creating the test database.",
    )
    parser.addini(
        "database_url",
        "The url to connect when creating the test database.",
    )


@pytest.fixture(scope="session")
def _database_url(request):
    def _get_name():
        tag = "".join(
            random.choice(string.ascii_lowercase + string.digits)
            for x in range(7)
        )
        return "linehousetest_{}".format(tag)

    def _check_name(engine, name):
        with engine.connect() as conn:
            results = conn.execute(
                "SELECT datname FROM pg_database WHERE datistemplate = false"
            )
            return name not in [r[0] for r in results]

    database_url_default = 'postgresql://localhost/test_linehaul'
    database_url_environ = os.environ.get("LINEHOUSE_DATABASE_URL")
    database_url_option = request.config.getvalue("database_url")

    if (not database_url_default and not database_url_environ
            and not database_url_option):
        pytest.skip("No database provided")

    # Configure our engine so that we can empty the database
    database_url = (
        database_url_option or database_url_environ or database_url_default
    )

    # Create the database schema
    engine = sqlalchemy.create_engine(
        database_url,
        poolclass=sqlalchemy.pool.NullPool,
    )

    with engine.connect() as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute("CREATE EXTENSION IF NOT EXISTS citext")
        conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option(
        "script_location",
        "linehaul:migrations",
    )
    alembic_cfg.set_main_option("url", database_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine.dispose()

    return database_url
