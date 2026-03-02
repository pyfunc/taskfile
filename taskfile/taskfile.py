import subprocess
import yaml
import os
from pathlib import Path

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Run taskfile with deployment options')
    parser.add_argument('--environment', '-e', default='development',
                       help='Deployment environment (development, staging, production)')
    args = parser.parse_args()

    task = Taskfile(environment=args.environment)
    task.deploy()

class Taskfile:
    def __init__(self, environment='development'):
        self.environment = environment
        self.config = self._load_config()
        self.validate_environment()

    def _load_config(self):
        config_path = Path('taskfile.yml')
        if not config_path.exists():
            raise FileNotFoundError('Configuration file taskfile.yml not found')

        with open(config_path, 'r') as file:
            return yaml.safe_load(file)

    def validate_environment(self):
        valid_environments = ['development', 'staging', 'production']
        if self.environment not in valid_environments:
            raise ValueError(f'Invalid environment. Must be one of: {valid_environments}')

    def deploy(self):
        if self.environment not in self.config:
            raise ValueError(f'No configuration found for environment: {self.environment}')

        env_config = self.config[self.environment]
        command = env_config.get('command')

        if not command:
            raise ValueError('No command specified in configuration')

        print(f'Deploying to {self.environment} environment...')
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            print(f'Error: {result.stderr}')
            return False

        print(result.stdout)
        return True