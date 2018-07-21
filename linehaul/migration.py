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

import itertools
import logging


logger = logging.getLogger(__name__)


_sentinel = object()


def validate_schema(existing, desired):
    # Loop over the existing schema, and the desired schema together, and look
    # for differences.
    for existing_item, new_item in itertools.zip_longest(
        existing, desired, fillvalue=_sentinel
    ):
        if new_item is _sentinel:
            raise ValueError("Cannot remove columns")
        elif existing_item is _sentinel:
            if new_item["mode"] not in {"NULLABLE", "REPEATED"}:
                raise ValueError(
                    f"Cannot add non NULLABLE/REPEATED column "
                    f"{new_item['name']!r} to existing schema."
                )
        else:
            if existing_item["name"] != new_item["name"]:
                raise ValueError(
                    f"Found column named {new_item['name']!r} in new schema when "
                    f"expected column named {existing_item['name']!r}"
                )

            if existing_item["type"] != new_item["type"]:
                raise ValueError(
                    f"Cannot change type of column {existing_item['name']!r} from "
                    f"{existing_item['type']!r} to {new_item['type']!r}."
                )

            if existing_item["mode"] != new_item["mode"] and not (
                existing_item["mode"] == "REQUIRED" and new_item["mode"] == "NULLABLE"
            ):
                raise ValueError(
                    f"Cannot change mode of column {existing_item['name']!r} except "
                    f"from REQUIRED to NULLABLE"
                )

            if existing_item["type"] == "RECORD":
                # Recurse into the record and validate the sub schema
                validate_schema(existing_item["fields"], new_item["fields"])


async def migrate(bq, table, new_schema):
    logger.info("Fetching existing schema for %r.", table)
    current_schema = await bq.get_schema(table)

    # If we have an existing schema, then we need to diff it against our desired schema,
    # and ensure that all of the changes we're making are backwardscompatible.
    if current_schema is not None:
        logger.info("Found existing schema, validating delta.")
        validate_schema(current_schema, new_schema)

    logger.info("Updating schema.")
    await bq.update_schema(table, new_schema)
    logger.info("Schema for %r updated.", table)
