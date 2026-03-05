from taskfile.cli.main import main
import taskfile.cli.deploy
import taskfile.cli.quadlet
import taskfile.cli.ci
import taskfile.cli.setup
import taskfile.cli.health
import taskfile.cli.release
import taskfile.cli.fleet
import taskfile.cli.auth
import taskfile.cli.interactive  # doctor, init, watch, graph
import taskfile.cli.cache_cmds   # cache management
import taskfile.cli.import_export  # import/export
import taskfile.cli.registry_cmds  # pkg install/search
import taskfile.cli.version  # version management (bump, show, set)
import taskfile.cli.docker_cmds  # docker management (stop, compose down, ports)

__all__ = ["main"]
