"""Global test configuration.

Mocks external dependencies (libtmux, fabric) that may not be installed
in the test environment.
"""

import sys
from unittest.mock import MagicMock

# Mock external dependencies before any chimera module imports them
for mod_name in ("libtmux", "fabric", "invoke"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
