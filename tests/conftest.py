"""Shared pytest fixtures for the test suite."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def silence_logger():
    """Suppress log output during tests to keep output clean."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture()
def mock_log():
    """Return a MagicMock that stands in for the module-level log object."""
    mock = MagicMock()
    mock.info = MagicMock()
    mock.warning = MagicMock()
    mock.error = MagicMock()
    mock.debug = MagicMock()
    return mock
