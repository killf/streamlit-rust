"""pytest configuration for the reference suite.

Setting ``sys.dont_write_bytecode`` here keeps ``__pycache__`` directories out
of the repository: the reference modules are imported by the test suite, and
without this every pytest run would leave build artefacts inside the write
set.
"""

import sys

sys.dont_write_bytecode = True
