"""Fixtures for Flask web GUI tests."""

import sys
from pathlib import Path

import pytest

# Ensure src/ is on path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'scripts'))

from web import create_app


@pytest.fixture
def app():
    """Create a Flask application for testing."""
    app = create_app(testing=True)
    yield app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
