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

import os.path

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if not hasattr(item, "module"):  # e.g.: DoctestTextfile
            continue

        module_path = os.path.relpath(
            item.module.__file__, os.path.commonprefix([__file__, item.module.__file__])
        )

        module_root_dir = module_path.split(os.pathsep)[0]
        if module_root_dir.startswith("unit"):
            item.add_marker(pytest.mark.unit)
