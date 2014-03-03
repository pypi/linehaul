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

import alembic.config
import alembic.command


def _create_alembic_config(database_url):
    alembic_cfg = alembic.config.Config()
    alembic_cfg.set_main_option("script_location", "linehaul:migrations")
    alembic_cfg.set_main_option("url", database_url)

    return alembic_cfg


def upgrade(config, revision):
    return alembic.command.upgrade(
        _create_alembic_config(config["database"]),
        revision=revision,
    )


def branches(config):
    return alembic.command.branches(_create_alembic_config(config["database"]))


def stamp(config, revision):
    return alembic.command.stamp(
        _create_alembic_config(config["database"]),
        revision=revision,
    )


def current(config, head_only):
    return alembic.command.current(
        _create_alembic_config(config["database"]),
        head_only=head_only,
    )


def downgrade(config, revision):
    return alembic.command.downgrade(
        _create_alembic_config(config["database"]),
        revision=revision,
    )


def history(config, rev_range):
    return alembic.command.history(
        _create_alembic_config(config["database"]),
        rev_range=rev_range,
    )


def revision(config, message, autogenerate):
    return alembic.command.revision(
        _create_alembic_config(config["database"]),
        message=message,
        autogenerate=autogenerate,
    )
