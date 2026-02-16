"""API routes for background task polling and JSON endpoints."""

from flask import Blueprint, jsonify, render_template, request

bp = Blueprint('api', __name__)


@bp.route('/task/<task_id>')
def task_status(task_id):
    """Return JSON status for a background task."""
    from web.tasks import get_task

    task = get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task)


@bp.route('/task/<task_id>/progress')
def task_progress(task_id):
    """HTML page that polls task status and redirects on completion."""
    redirect_to = request.args.get('redirect_to', '/')
    from web.tasks import get_task

    task = get_task(task_id)
    task_name = task['name'] if task else 'Unknown'

    return render_template(
        '_task_progress.html',
        task_id=task_id,
        task_name=task_name,
        redirect_to=redirect_to,
    )
