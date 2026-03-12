"""
Shared fixtures for backend unit tests.

Adds the backend directory to sys.path so that imports like
``from models.user import User`` work without installing
the package.
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure the backend package root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Environment – set safe defaults *before* any production module is imported
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "15")
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DBNAME", "spy_among_us_test")
os.environ.setdefault("DEBUG", "True")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis_client():
    """Return an AsyncMock that mimics RedisClient."""
    client = AsyncMock()
    client.get_user.return_value = {}
    client.cache_room.return_value = True
    client.check_room_exists.return_value = True
    client.get_room_users.return_value = set()
    client.get_room_users_count.return_value = 0
    client.get_room_basic_data.return_value = {}
    client.is_user_in_room.return_value = False
    client.get_room_ready_users.return_value = set()
    return client


@pytest.fixture
def mock_mongo_client():
    """Return an AsyncMock that mimics MongoClient."""
    client = AsyncMock()
    client.find_user_by_username.return_value = None
    client.create_user.return_value = True
    client.get_user.return_value = None
    return client


@pytest.fixture
def mock_websocket_manager():
    """Return an AsyncMock that mimics WebSocketManager."""
    manager = AsyncMock()
    manager.broadcast_message.return_value = None
    manager.close_room_connections.return_value = None
    return manager
