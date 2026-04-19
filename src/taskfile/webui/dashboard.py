"""Dashboard HTML template for the taskfile web UI."""

from __future__ import annotations


def get_dashboard_html() -> str:
    """Return the full dashboard HTML page."""
    return _CSS + _BODY + _SCRIPT


_CSS = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Taskfile Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
        }
        .header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .header h1 {
            font-size: 1.5rem;
            color: #58a6ff;
        }
        .header .badge {
            background: #238636;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-size: 0.75rem;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 0.5rem;
            padding: 1.5rem;
        }
        .stat-card h3 {
            font-size: 0.875rem;
            color: #8b949e;
            margin-bottom: 0.5rem;
        }
        .stat-card .value {
            font-size: 2rem;
            font-weight: 600;
            color: #58a6ff;
        }
        .section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }
        .section-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #30363d;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .section-content {
            padding: 1rem;
        }
        .task-list {
            list-style: none;
        }
        .task-item {
            display: flex;
            align-items: center;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #21262d;
            gap: 1rem;
        }
        .task-item:last-child {
            border-bottom: none;
        }
        .task-item:hover {
            background: #21262d;
        }
        .task-name {
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 0.875rem;
            color: #7ee787;
            min-width: 150px;
        }
        .task-desc {
            color: #8b949e;
            flex: 1;
        }
        .task-deps {
            font-size: 0.75rem;
            color: #8b949e;
        }
        .task-deps span {
            background: #21262d;
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            margin-right: 0.25rem;
        }
        .run-btn {
            background: #238636;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.875rem;
            transition: background 0.2s;
        }
        .run-btn:hover {
            background: #2ea043;
        }
        .run-btn:disabled {
            background: #484f58;
            cursor: not-allowed;
        }
        .env-badge {
            background: #1f6feb;
            color: white;
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
        }
        .tag-badge {
            background: #8957e5;
            color: white;
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
        }
        .output-panel {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 1rem;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 0.75rem;
            white-space: pre-wrap;
        }
        .output-panel.success {
            border-left: 3px solid #238636;
        }
        .output-panel.error {
            border-left: 3px solid #f85149;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #30363d;
            border-top: 2px solid #58a6ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .search-box {
            width: 100%;
            padding: 0.75rem 1rem;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 0.375rem;
            color: #c9d1d9;
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }
        .search-box:focus {
            outline: none;
            border-color: #58a6ff;
        }
        .filter-tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
            padding: 0 1rem;
        }
        .filter-tab {
            background: transparent;
            border: 1px solid #30363d;
            color: #8b949e;
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.875rem;
        }
        .filter-tab.active {
            background: #1f6feb;
            color: white;
            border-color: #1f6feb;
        }
        .hidden {
            display: none;
        }
    </style>
</head>"""

_BODY = """
<body>
    <div class="header">
        <h1>\U0001f4cb Taskfile Dashboard</h1>
        <span class="badge" id="task-count">0 tasks</span>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>Tasks</h3>
                <div class="value" id="stat-tasks">0</div>
            </div>
            <div class="stat-card">
                <h3>Environments</h3>
                <div class="value" id="stat-envs">0</div>
            </div>
            <div class="stat-card">
                <h3>Platforms</h3>
                <div class="value" id="stat-platforms">0</div>
            </div>
            <div class="stat-card">
                <h3>Variables</h3>
                <div class="value" id="stat-vars">0</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                \U0001f4c1 Project Info
            </div>
            <div class="section-content" id="project-info">
                <p>Loading...</p>
            </div>
        </div>
        
        <div class="section">
            <div class="section-header">
                \U0001f527 Available Tasks
            </div>
            <div class="section-content">
                <input type="text" class="search-box" id="search" placeholder="Search tasks...">
                <div class="filter-tabs">
                    <button class="filter-tab active" onclick="filterTasks('all')">All</button>
                    <button class="filter-tab" onclick="filterTasks('local')">Local</button>
                    <button class="filter-tab" onclick="filterTasks('remote')">Remote</button>
                </div>
                <ul class="task-list" id="task-list">
                    <li class="task-item">Loading tasks...</li>
                </ul>
            </div>
        </div>
        
        <div class="section hidden" id="output-section">
            <div class="section-header">
                \U0001f4e4 Output
            </div>
            <div class="section-content">
                <div class="output-panel" id="output-panel"></div>
            </div>
        </div>
    </div>"""

_SCRIPT = """
    <script>
        let allTasks = [];
        let config = {};
        
        // Load data
        async function loadData() {
            try {
                const [tasksRes, configRes] = await Promise.all([
                    fetch('/api/tasks'),
                    fetch('/api/config')
                ]);
                
                const tasksData = await tasksRes.json();
                config = await configRes.json();
                
                allTasks = tasksData.tasks || [];
                renderTasks(allTasks);
                renderStats();
                renderProjectInfo();
            } catch (e) {
                document.getElementById('task-list').innerHTML = 
                    '<li class="task-item">Error loading tasks: ' + e.message + '</li>';
            }
        }
        
        function renderStats() {
            document.getElementById('stat-tasks').textContent = allTasks.length;
            document.getElementById('stat-envs').textContent = config.environments?.length || 0;
            document.getElementById('stat-platforms').textContent = config.platforms?.length || 0;
            document.getElementById('stat-vars').textContent = config.variables?.length || 0;
            document.getElementById('task-count').textContent = allTasks.length + ' tasks';
        }
        
        function renderProjectInfo() {
            const html = `
                <h2>${config.name || 'Unnamed Project'}</h2>
                <p style="color: #8b949e; margin-top: 0.5rem;">${config.description || 'No description'}</p>
                <div style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    ${(config.environments || []).map(e => `<span class="env-badge">${e}</span>`).join('')}
                </div>
            `;
            document.getElementById('project-info').innerHTML = html;
        }
        
        function renderTasks(tasks) {
            const list = document.getElementById('task-list');
            
            if (tasks.length === 0) {
                list.innerHTML = '<li class="task-item">No tasks found</li>';
                return;
            }
            
            list.innerHTML = tasks.map(task => `
                <li class="task-item" data-env="${task.env_filter?.join(',') || 'all'}">
                    <span class="task-name">${task.name}</span>
                    <span class="task-desc">${task.description || 'No description'}</span>
                    <span class="task-deps">
                        ${(task.deps || []).map(d => `<span>${d}</span>`).join('')}
                        ${(task.tags || []).map(t => `<span class="tag-badge">${t}</span>`).join('')}
                    </span>
                    <button class="run-btn" onclick="runTask('${task.name}')">Run</button>
                </li>
            `).join('');
        }
        
        function filterTasks(type) {
            // Update active tab
            document.querySelectorAll('.filter-tab').forEach(tab => {
                tab.classList.toggle('active', tab.textContent.toLowerCase() === type);
            });
            
            // Filter tasks
            let filtered = allTasks;
            if (type === 'local') {
                filtered = allTasks.filter(t => !t.env_filter || t.env_filter.includes('local'));
            } else if (type === 'remote') {
                filtered = allTasks.filter(t => t.env_filter && !t.env_filter.includes('local'));
            }
            
            // Also apply search filter
            const search = document.getElementById('search').value.toLowerCase();
            if (search) {
                filtered = filtered.filter(t => 
                    t.name.toLowerCase().includes(search) ||
                    (t.description && t.description.toLowerCase().includes(search))
                );
            }
            
            renderTasks(filtered);
        }
        
        async function runTask(name) {
            const outputSection = document.getElementById('output-section');
            const outputPanel = document.getElementById('output-panel');
            
            outputSection.classList.remove('hidden');
            outputPanel.className = 'output-panel';
            outputPanel.innerHTML = '<div class="loading"></div> Running ' + name + '...';
            
            try {
                const res = await fetch('/api/run/' + encodeURIComponent(name), {method: 'POST'});
                const data = await res.json();
                
                outputPanel.innerHTML = data.message || 'Task started';
                outputPanel.classList.add('success');
            } catch (e) {
                outputPanel.innerHTML = 'Error: ' + e.message;
                outputPanel.classList.add('error');
            }
            
            // Scroll to output
            outputSection.scrollIntoView({behavior: 'smooth'});
        }
        
        // Search functionality
        document.getElementById('search').addEventListener('input', (e) => {
            const search = e.target.value.toLowerCase();
            const filtered = allTasks.filter(t => 
                t.name.toLowerCase().includes(search) ||
                (t.description && t.description.toLowerCase().includes(search))
            );
            renderTasks(filtered);
        });
        
        // Load on start
        loadData();
    </script>
</body>
</html>
"""
