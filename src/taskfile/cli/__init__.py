from taskfile.cli.main import main
import taskfile.cli.deploy
import taskfile.cli.quadlet
import taskfile.cli.ci
import taskfile.cli.setup
import taskfile.cli.health
import taskfile.cli.release
import taskfile.cli.fleet
import taskfile.cli.auth
import taskfile.cli.interactive  # NEW: doctor, interactive init, watch
import taskfile.cli.cache_cmds  # NEW: cache management

__all__ = ["main"]
