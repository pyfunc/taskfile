from taskfile.cli.main import main
import taskfile.cli.deploy
import taskfile.cli.quadlet
import taskfile.cli.ci
import taskfile.cli.setup
import taskfile.cli.health
import taskfile.cli.release
import taskfile.cli.fleet
import taskfile.cli.auth
import taskfile.cli.interactive  # doctor, interactive init, watch, graph
import taskfile.cli.cache_cmds  # cache management
import taskfile.cli.import_export  # import/export converters

__all__ = ["main"]
