"""Web UI server package for taskfile - dashboard in browser.

Split from webui.py for maintainability.
All public symbols are re-exported here for backward compatibility.
"""

from taskfile.webui.server import WebUIServer, serve_dashboard

__all__ = ["WebUIServer", "serve_dashboard"]
