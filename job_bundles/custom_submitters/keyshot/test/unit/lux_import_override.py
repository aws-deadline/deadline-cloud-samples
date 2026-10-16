# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import sys
from unittest.mock import Mock

# Because the `lux` module doesn't exist in standard Python, imports of `lux` will fail in tests.
# To avoid this, we replace the lux module with a mock.
# To use this, add
# `from .. import lux_import_override  # noqa F401`
# to the top of your test file.
module_name = "lux"
lux_module = Mock()
sys.modules[module_name] = lux_module
