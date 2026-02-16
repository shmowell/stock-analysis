"""
Background task runner using threading.

Simple in-memory task store for a local single-user tool.
No external dependencies (no Celery, no Redis).
"""

import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional

_tasks: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def submit_task(name: str, func: Callable, *args, **kwargs) -> str:
    """Submit a function to run in a background thread.

    Args:
        name: Human-readable task name.
        func: Callable to run.
        *args, **kwargs: Passed to func.

    Returns:
        task_id string for polling via /api/task/<id>.
    """
    task_id = str(uuid.uuid4())[:8]
    with _lock:
        _tasks[task_id] = {
            'name': name,
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'result': None,
            'error': None,
        }

    def _run():
        try:
            result = func(*args, **kwargs)
            with _lock:
                _tasks[task_id]['status'] = 'completed'
                _tasks[task_id]['result'] = result
        except Exception as e:
            with _lock:
                _tasks[task_id]['status'] = 'failed'
                _tasks[task_id]['error'] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task status by ID."""
    with _lock:
        return _tasks.get(task_id, {}).copy() if task_id in _tasks else None
