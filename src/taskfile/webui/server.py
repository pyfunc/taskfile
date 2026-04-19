"""Web UI server — HTTP server wrapper and entry point."""

from __future__ import annotations

import webbrowser
from http.server import HTTPServer

from taskfile.webui.handlers import TaskfileHandler


class WebUIServer:
    """Web UI server for taskfile."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.server: HTTPServer | None = None

    def start(self, open_browser: bool = True) -> None:
        """Start the web UI server."""
        self.server = HTTPServer(("localhost", self.port), TaskfileHandler)

        url = f"http://localhost:{self.port}"
        print(f"🌐 Taskfile Web UI running at {url}")

        if open_browser:
            webbrowser.open(url)

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            self.stop()

    def stop(self) -> None:
        """Stop the server."""
        if self.server:
            self.server.shutdown()


def serve_dashboard(port: int = 8080, open_browser: bool = True) -> None:
    """Start the web dashboard."""
    server = WebUIServer(port)
    server.start(open_browser)
