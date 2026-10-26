"""Pytest session-wide fixtures for JOV.si."""

import threading
import time
import pytest
import uvicorn

from mock_portal.server import app as mock_app, reset_mock_portal

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 8765
MOCK_BASE_URL = f"http://{MOCK_HOST}:{MOCK_PORT}"


@pytest.fixture(scope="session")
def mock_server():
    """Start mock portal server once for the entire pytest test session."""
    config = uvicorn.Config(mock_app, host=MOCK_HOST, port=MOCK_PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.0)  # Wait for startup
    yield MOCK_BASE_URL
    server.should_exit = True


@pytest.fixture(autouse=True)
def clean_mock_state():
    """Reset mock portal state before each test."""
    reset_mock_portal()
    yield
    reset_mock_portal()
