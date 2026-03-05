"""HTTP request handler for taskfile web UI — routing, API, dashboard HTML."""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taskfile.models import TaskfileConfig


class TaskfileHandler(BaseHTTPRequestHandler):
    """HTTP request handler for taskfile web UI."""
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET requests."""
        path = self.path
        
        if path == '/' or path == '/index.html':
            self._serve_html()
        elif path == '/api/tasks':
            self._serve_tasks_json()
        elif path == '/api/config':
            self._serve_config_json()
        elif path.startswith('/api/run/'):
            task_name = path[9:]  # Remove /api/run/
            self._run_task(task_name)
        elif path == '/favicon.ico':
            self._send_404()
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path.startswith('/api/run/'):
            task_name = self.path[9:]
            self._run_task(task_name)
        else:
            self._send_404()
    
    def _serve_html(self):
        """Serve the main dashboard HTML."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html = self._get_dashboard_html()
        self.wfile.write(html.encode('utf-8'))
    
    def _serve_tasks_json(self):
        """Serve tasks as JSON."""
        try:
            from taskfile.parser import load_taskfile
            config = load_taskfile()
            
            tasks = []
            for name, task in config.tasks.items():
                tasks.append({
                    'name': name,
                    'description': task.description or '',
                    'deps': list(task.deps) if task.deps else [],
                    'env_filter': list(task.env_filter) if task.env_filter else [],
                    'platform_filter': list(task.platform_filter) if task.platform_filter else [],
                    'parallel': task.parallel,
                    'ignore_errors': task.ignore_errors,
                    'retries': task.retries,
                    'tags': list(task.tags) if task.tags else [],
                })
            
            self._send_json({'tasks': tasks})
        except Exception as e:
            self._send_json({'error': str(e)}, status=500)
    
    def _serve_config_json(self):
        """Serve configuration as JSON."""
        try:
            from taskfile.parser import load_taskfile
            config = load_taskfile()
            
            self._send_json({
                'name': config.name,
                'description': config.description,
                'version': config.version,
                'environments': list(config.environments.keys()),
                'platforms': list(config.platforms.keys()),
                'variables': list(config.variables.keys()),
            })
        except Exception as e:
            self._send_json({'error': str(e)}, status=500)
    
    def _run_task(self, task_name: str):
        """Run a task via API."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        # Run task in background thread
        def run():
            try:
                result = subprocess.run(
                    ['taskfile', 'run', task_name],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return {
                    'success': result.returncode == 0,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode,
                }
            except subprocess.TimeoutExpired:
                return {'success': False, 'error': 'Timeout'}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        # For now, just acknowledge
        self.wfile.write(json.dumps({
            'message': f'Task "{task_name}" started',
            'status': 'running',
        }).encode())
    
    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_404(self):
        """Send 404 response."""
        self.send_response(404)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not found')
    
    def _get_dashboard_html(self) -> str:
        """Generate the dashboard HTML."""
        from taskfile.webui.dashboard import get_dashboard_html
        return get_dashboard_html()
