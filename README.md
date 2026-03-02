# taskfile

Python package for running taskfile with deployment options for different environments.

## Installation

```bash
pip install taskfile
```

## Usage

```python
from taskfile import Taskfile

# Initialize with environment
task = Taskfile(environment='production')

# Run deployment
task.deploy()
```

## Available Environments

- `development`
- `staging`
- `production`

## Configuration

Create a `taskfile.yml` configuration file in your project root.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
