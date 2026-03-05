"""Interactive CLI commands package — doctor, init wizard, setup, watch, graph, serve.

Split from interactive.py for maintainability.
All commands are registered via submodule imports.
"""

import taskfile.cli.interactive.wizards  # noqa: F401 — registers doctor, init
import taskfile.cli.interactive.menu  # noqa: F401 — registers setup, watch, graph, serve
