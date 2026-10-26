"""Pytest fixtures for isolated SmartBrew tests."""

import pytest
from src.database import initialize_database

@pytest.fixture
def db_path(tmp_path):
    """Create a fresh seeded database for a test.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to the isolated SQLite database.
    """
    path = tmp_path / "test_smartbrew.db"
    initialize_database(path)
    return str(path)
